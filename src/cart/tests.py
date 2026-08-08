import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.conf import settings
from django.db import connection
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from unittest import skipUnless

from cart.models import Order, PaymentAttempt
from cart.views.order import _get_payment_url
from cart.views.tpay import payment_callback, tinkoff_token


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

        def invoke():
            factory = RequestFactory()
            return payment_callback(factory.post(
                "/api/payments/callback/", data=json.dumps(body), content_type="application/json"
            )).status_code

        # SQLite serialises writers differently from production PostgreSQL, but
        # this test still starts two independent concurrent callback requests.
        with patch("cart.views.tpay.send_tg_order_status") as tg, patch(
            "cart.views.tpay.send_order_status_changed_email"
        ) as email, ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda _: invoke(), range(2)))

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

    @skipUnless(connection.vendor == "postgresql", "concurrent init requires PostgreSQL")
    def test_concurrent_get_payment_url_does_not_create_two_attempts(self):
        order = self.order
        request = self.request

        def invoke():
            with patch("cart.views.order.create_PaymentURL", return_value=("https://pay.example/1", "payment-init-1")):
                return _get_payment_url(order, request)

        with ThreadPoolExecutor(max_workers=2) as pool:
            urls = list(pool.map(lambda _: invoke(), range(2)))

        self.assertEqual(urls, ["https://pay.example/1", "https://pay.example/1"])
        self.assertEqual(PaymentAttempt.objects.count(), 1)
