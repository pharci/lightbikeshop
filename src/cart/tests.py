import json
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.conf import settings
from django.db import connection, connections, close_old_connections
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from unittest import skipUnless

from cart.models import Order, PaymentAttempt
from cart.views.order import _get_payment_url, _attempt_bank_order_id
from cart.views.tpay import payment_callback, tinkoff_token
from django.urls import reverse


@override_settings(T_BANK_TERMINAL_KEY="TEST", T_BANK_PASSWORD="secret")
class PaymentCallbackTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            user_name="Test Customer",
            contact_phone="+7 (999) 000-00-00",
            total="123.45",
            payment_id="payment-1",
        )
        self.factory = RequestFactory()

    def callback(self, **overrides):
        token_override = overrides.pop("Token", None)
        body = {
            "TerminalKey": settings.T_BANK_TERMINAL_KEY,
            "OrderId": self.order.order_id,
            "PaymentId": "payment-1",
            "Amount": 12345,
            "Success": True,
            "Status": "CONFIRMED",
        }
        body.update(overrides)
        body["Token"] = tinkoff_token(body, settings.T_BANK_PASSWORD)
        if token_override is not None:
            body["Token"] = token_override
        return payment_callback(
            self.factory.post("/api/payments/callback/", data=json.dumps(body), content_type="application/json")
        )

    @patch("cart.views.tpay.send_order_status_changed_email")
    @patch("cart.views.tpay.send_tg_order_status")
    def test_valid_confirmed_callback_marks_paid_once(self, tg, email):
        self.assertEqual(self.callback().status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "paid")
        self.assertEqual(tg.call_count, 1)
        self.assertEqual(email.call_count, 1)

        self.assertEqual(self.callback().status_code, 200)
        self.assertEqual(tg.call_count, 1)
        self.assertEqual(email.call_count, 1)

    def test_invalid_token_cannot_change_order(self):
        response = self.callback(Token="bad")
        self.assertEqual(response.status_code, 400)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "created")

    def test_wrong_amount_or_payment_id_cannot_change_order(self):
        self.assertEqual(self.callback(Amount=1).status_code, 400)
        self.assertEqual(self.callback(PaymentId="another-payment").status_code, 400)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "created")

    def test_authorized_is_not_paid_and_rejected_is_not_paid(self):
        self.assertEqual(self.callback(Status="AUTHORIZED").status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "auth")

        rejected = Order.objects.create(
            user_name="Rejected Customer", contact_phone="+7 (999) 000-00-01",
            total="123.45", payment_id="payment-2",
        )
        self.order = rejected
        self.assertEqual(self.callback(PaymentId="payment-2", Success=False, Status="REJECTED").status_code, 200)
        rejected.refresh_from_db()
        self.assertEqual(rejected.status, "declined")


@override_settings(T_BANK_TERMINAL_KEY="TEST", T_BANK_PASSWORD="secret")
@skipUnless(connection.vendor == "postgresql", "row-lock concurrency requires PostgreSQL")
class ConcurrentPaymentCallbackTests(TransactionTestCase):
    """This intentionally makes two HTTP-style callback invocations in parallel."""

    reset_sequences = True

    @classmethod
    def tearDownClass(cls):
        connections.close_all()
        close_old_connections()
        super().tearDownClass()

    def tearDown(self):
        connections.close_all()
        close_old_connections()

    def _invoke_callback(self, body):
        connections.close_all()
        close_old_connections()
        factory = RequestFactory()
        try:
            return payment_callback(factory.post(
                "/api/payments/callback/", data=json.dumps(body), content_type="application/json"
            )).status_code
        finally:
            connections.close_all()
            close_old_connections()

    def test_two_confirmations_emit_one_notification(self):
        order = Order.objects.create(
            user_name="Concurrent Customer", contact_phone="+7 (999) 000-00-02",
            total="123.45", payment_id="payment-concurrent",
        )
        body = {
            "TerminalKey": "TEST", "OrderId": order.order_id,
            "PaymentId": "payment-concurrent", "Amount": 12345,
            "Success": True, "Status": "CONFIRMED",
        }
        body["Token"] = tinkoff_token(body, "secret")

        # SQLite serialises writers differently from production PostgreSQL, but
        # this test still starts two independent concurrent callback requests.
        with patch("cart.views.tpay.send_tg_order_status") as tg, patch(
            "cart.views.tpay.send_order_status_changed_email"
        ) as email, ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda _: self._invoke_callback(body), range(2)))

        self.assertEqual(statuses, [200, 200])
        order.refresh_from_db()
        self.assertEqual(order.status, "paid")
        self.assertEqual(tg.call_count, 1)
        self.assertEqual(email.call_count, 1)


@override_settings(T_BANK_TERMINAL_KEY="TEST", T_BANK_PASSWORD="secret")
class PaymentInitRecoveryTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            user_name="Init Customer", contact_phone="+7 (999) 000-00-03", total="123.45"
        )
        self.request = RequestFactory().post("/cart/checkout/")

    @patch("cart.views.order.create_PaymentURL", return_value=("https://pay.example/1", "payment-init-1"))
    def test_existing_active_attempt_is_reused_without_second_init(self, init):
        self.assertEqual(_get_payment_url(self.order, self.request), "https://pay.example/1")
        self.assertEqual(_get_payment_url(self.order, self.request), "https://pay.example/1")
        self.assertEqual(init.call_count, 1)
        self.assertEqual(PaymentAttempt.objects.count(), 1)

    @patch("cart.views.order.create_PaymentURL", side_effect=TimeoutError)
    def test_timeout_never_causes_a_second_init(self, init):
        with self.assertRaises(TimeoutError):
            _get_payment_url(self.order, self.request)
        attempt = PaymentAttempt.objects.get()
        self.assertEqual(attempt.state, "init_unknown")

        with patch("cart.views.order.check_order", return_value=None):
            with self.assertRaises(RuntimeError):
                _get_payment_url(self.order, self.request)
        self.assertEqual(init.call_count, 1)

    @patch("cart.views.order.create_PaymentURL", side_effect=TimeoutError)
    def test_timeout_recovery_uses_bank_confirmed_existing_session(self, init):
        with self.assertRaises(TimeoutError):
            _get_payment_url(self.order, self.request)
        with patch("cart.views.order.check_order", return_value={
            "Success": True, "PaymentId": "payment-recovered", "PaymentURL": "https://pay.example/recovered"
        }):
            self.assertEqual(_get_payment_url(self.order, self.request), "https://pay.example/recovered")
        attempt = PaymentAttempt.objects.get()
        self.assertEqual((attempt.state, attempt.payment_id), ("active", "payment-recovered"))
        self.assertEqual(init.call_count, 1)

    @patch("cart.views.order.create_PaymentURL", return_value=("https://pay.example/recovered", "payment-recovered"))
    @patch("cart.views.order.check_order", return_value={
        "Success": True, "PaymentId": "payment-recovered", "PaymentURL": "https://pay.example/recovered"
    })
    def test_recovery_finds_existing_payment_and_does_not_init_again(self, check_order, init):
        attempt = PaymentAttempt.objects.create(
            order=self.order,
            bank_order_id=_attempt_bank_order_id(self.order),
            state="init_pending",
        )

        url = _get_payment_url(self.order, self.request)

        self.assertEqual(url, "https://pay.example/recovered")
        self.assertEqual(init.call_count, 0)
        self.assertEqual(check_order.call_count, 1)
        self.assertEqual(PaymentAttempt.objects.filter(order=self.order).count(), 1)
        attempt.refresh_from_db()
        self.assertEqual(attempt.state, "active")
        self.assertEqual(attempt.payment_id, "payment-recovered")
        self.assertEqual(attempt.payment_url, "https://pay.example/recovered")

    @patch("cart.views.order.create_PaymentURL", return_value=("https://pay.example/new-init", "payment-init-2"))
    @patch("cart.views.order.check_order", return_value={"Success": False, "Status": "REJECTED"})
    def test_terminal_check_order_allows_new_init(self, check_order, init):
        attempt = PaymentAttempt.objects.create(
            order=self.order,
            bank_order_id=_attempt_bank_order_id(self.order),
            state="init_pending",
        )

        url = _get_payment_url(self.order, self.request)

        self.assertEqual(url, "https://pay.example/new-init")
        self.assertEqual(init.call_count, 1)
        self.assertEqual(check_order.call_count, 1)
        self.assertEqual(PaymentAttempt.objects.filter(order=self.order).count(), 2)
        self.assertEqual(PaymentAttempt.objects.filter(order=self.order, state="active").count(), 1)


@override_settings(T_BANK_TERMINAL_KEY="TEST", T_BANK_PASSWORD="secret")
@skipUnless(connection.vendor == "postgresql", "concurrent init requires PostgreSQL")
class ConcurrentGetPaymentURLTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        order = Order.objects.create(
            user_name="Concurrent Init Customer",
            contact_phone="+7 (999) 000-00-04",
            total="123.45"
        )
        self.order_id = order.pk
        self.order = order
        self.request = RequestFactory().post("/cart/checkout/")
        # Ensure the object is committed to the DB before worker threads use separate connections.
        connection.commit()

    @classmethod
    def tearDownClass(cls):
        connections.close_all()
        close_old_connections()
        super().tearDownClass()

    def tearDown(self):
        connections.close_all()
        close_old_connections()

    def _invoke_get_payment_url(self, barrier):
        connections.close_all()
        close_old_connections()
        order = Order.objects.get(pk=self.order_id)
        request = RequestFactory().post("/cart/checkout/")
        barrier.wait()
        try:
            return _get_payment_url(order, request)
        finally:
            connections.close_all()
            close_old_connections()

    def test_concurrent_get_payment_url_does_not_create_two_attempts(self):
        barrier = threading.Barrier(2)

        with patch("cart.views.order.create_PaymentURL", return_value=("https://pay.example/1", "payment-init-1")) as init:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(self._invoke_get_payment_url, barrier) for _ in range(2)]
                urls = [future.result() for future in futures]

            self.assertEqual(init.call_count, 1)
            for future in futures:
                self.assertTrue(future.done())
                self.assertIsNone(future.exception())

        connections.close_all()
        close_old_connections()

        self.order.refresh_from_db()
        self.assertEqual(urls, ["https://pay.example/1", "https://pay.example/1"])
        self.assertEqual(PaymentAttempt.objects.filter(order=self.order).count(), 1)
        self.assertEqual(PaymentAttempt.objects.count(), 1)
        self.assertEqual(self.order.payment_attempts.count(), 1)


class PvzApiTests(TestCase):
    def test_get_cities_returns_list(self):
        # mock external CDEK HTTP call
        with patch('cart.views.cdek._get_token', return_value='fake-token'):
            with patch('cart.views.cdek.requests.get') as req_get:
                mock_resp = req_get.return_value
                mock_resp.raise_for_status.return_value = None
                mock_resp.json.return_value = [
                    {'code': '520', 'city': 'TestCity', 'region': 'MO'}
                ]

                res = self.client.get('/api/pvz/cities/', secure=True, follow=True)
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertIsInstance(data, list)
                self.assertEqual(data[0]['city'], 'TestCity')

                # ensure the module's requests.get was called (mock applied correctly)
                self.assertTrue(req_get.called)
                req_get.assert_called()

    def test_api_cdek_pvz_returns_points_for_city(self):
        # patch internal helper to avoid external calls
        with patch('cart.views.cdek.get_pvz_by_city_code') as gp:
            gp.return_value = [
                {'id': '1', 'name': 'PVZ1', 'address': 'Addr', 'lat': 55.0, 'lon': 37.0, 'provider': 'cdek'}
            ]

            res = self.client.get('/api/pvz/cdek/?city_code=520', secure=True, follow=True)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertIsInstance(data, list)
            self.assertEqual(data[0]['provider'], 'cdek')

            # ensure the helper was called
            self.assertTrue(gp.called)
            gp.assert_called_once_with(520)
