# views.py
import json, logging, hashlib, requests
from urllib.parse import parse_qs

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import IntegrityError, transaction

from cart.models import Order, PaymentAttempt
from cart.MS import set_ms_order_state_by_uuid
from cart.order_utils import as_kop, D, allocate_lines
from accounts.telegram import send_tg_order_status
from accounts.email import send_order_status_changed_email

logger = logging.getLogger(__name__)

def build_receipt(order):
    subtotal = D(order.subtotal or 0)              # сумма товаров до скидки
    shipping = D(order.shipping_total or 0)        # доставка
    order_total = D(order.total or 0)              # финальная сумма
    goods_total = max(D("0.00"), order_total - shipping)

    # распределяем скидку только по товарам
    pairs = [(it.variant, it.quantity) for it in order.items.all()]
    lines = allocate_lines(pairs, subtotal, goods_total)  # [{variant, quantity, amount_kop}]

    items = []

    for l in lines:
        name = l["variant"].display_name()[:128]
        qty  = int(l["quantity"])
        amt  = int(l["amount_kop"])  # копейки на строку

        base = amt // qty
        rest = amt % qty
        lo_qty = qty - rest
        if lo_qty:
            items.append({
                "Name": name,
                "Price": base,
                "Quantity": lo_qty,
                "Amount": base * lo_qty,
                "Tax": "none",
                "PaymentMethod": "full_prepayment",
                "PaymentObject": "commodity",
            })
        if rest:
            items.append({
                "Name": name,
                "Price": base + 1,
                "Quantity": rest,
                "Amount": (base + 1) * rest,
                "Tax": "none",
                "PaymentMethod": "full_prepayment",
                "PaymentObject": "commodity",
            })

    # доставка отдельной услугой
    ship_amt = as_kop(shipping)
    if ship_amt > 0:
        items.append({
            "Name": "Доставка",
            "Price": ship_amt,
            "Quantity": 1,
            "Amount": ship_amt,
            "Tax": "none",
            "PaymentMethod": "full_prepayment",
            "PaymentObject": "service",
        })

    return {
        "Email": order.email,
        "Phone": order.contact_phone,
        "Taxation": "usn_income",
        "Items": items,
        "CompanyEmail": "lightbikeshop@yandex.ru",
    }


def tinkoff_token(params: dict, secret_key: str) -> str:
    data = {}
    for k, v in params.items():
        if k in ("Token", "Receipt") or v is None:
            continue
        if isinstance(v, bool):
            v = "true" if v else "false"
        data[k] = str(v)
    data["Password"] = secret_key
    s = "".join(data[k] for k in sorted(data))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _tbank_request_payload(**params):
    params["TerminalKey"] = settings.T_BANK_TERMINAL_KEY
    params["Token"] = tinkoff_token(params, settings.T_BANK_PASSWORD)
    return params


def check_order(bank_order_id):
    """Ask T-Bank whether an Init whose response was lost created a payment."""
    payload = _tbank_request_payload(OrderId=str(bank_order_id))
    try:
        response = requests.post("https://securepay.tinkoff.ru/v2/CheckOrder", json=payload, timeout=15)
        response.raise_for_status()
    except requests.RequestException:
        return None

    try:
        data = response.json()
    except ValueError:
        return None

    if data.get("Success") is True:
        return data

    status = str(data.get("Status") or "").upper()
    if status in ("AUTHORIZED", "CONFIRMED", "REJECTED", "CANCELED", "EXPIRED"):
        return data

    return None


def create_PaymentURL(order, request, bank_order_id=None):
    url = "https://securepay.tinkoff.ru/v2/Init"
    payload = {
        "TerminalKey": settings.T_BANK_TERMINAL_KEY,
        "OrderId": str(bank_order_id or order.order_id),
        "Amount": int(D(order.total or 0) * 100),  # копейки с нового поля total
        "PayType": "O",
        "SuccessURL": request.build_absolute_uri(order.get_absolute_url()),
        "FailURL": request.build_absolute_uri(order.get_absolute_url()),
        "NotificationURL": request.build_absolute_uri("/api/payments/callback/"),
        "Receipt": build_receipt(order),
    }
    payload["Token"] = tinkoff_token(payload, settings.T_BANK_PASSWORD)

    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    data = r.json()
    if not data.get("Success") or not data.get("PaymentId") or not data.get("PaymentURL"):
        raise Exception(f"Init error: {data}")
    return data["PaymentURL"], str(data["PaymentId"])

# @csrf_exempt
# @require_POST
# def payment_callback(request):
#     ct = request.META.get("CONTENT_TYPE","").lower()
#     b = request.body.decode("utf-8") if request.body else ""
#     try:
#         d = json.loads(b) if b and "json" in ct else {}
#     except json.JSONDecodeError:
#         d = {}
#     if not d and b:
#         d = {k:v[0] for k,v in parse_qs(b).items()}
#     if not d:
#         return HttpResponse("BAD BODY", status=400)

#     if str(d.get("Token","")).lower() != tinkoff_token(d, settings.T_BANK_PASSWORD).lower():
#         return HttpResponse("BAD TOKEN", status=400)

#     try:
#         order = Order.objects.get(order_id=d.get("OrderId"))
#     except Order.DoesNotExist:
#         return HttpResponse("NO ORDER", status=404)

#     status = str(d.get("Status","")).upper()
#     success = (str(d.get("Success","")).lower() == "true")

#     if success and status in ("CONFIRMED", "AUTHORIZED"):
#         changed = False
#         with transaction.atomic():
#             o = Order.objects.select_for_update().get(pk=order.pk)
#             if o.status != "paid":
#                 o.status = "paid"
#                 o.save(update_fields=["status", "updated"])
#                 changed = True
#                 oid = o.order_id
#                 ms_id = o.ms_order_id

#         if changed:
#             def _after_commit(oid=oid, ms_id=ms_id):
#                 try:
#                     set_ms_order_state_by_uuid(ms_id, 'db567a2a-9f5a-11ef-0a80-176f007f7c59')
#                 except Exception:
#                     pass
#                 try:
#                     oo = Order.objects.filter(order_id=oid).only("pk").first()
#                     if oo:
#                         send_order_status_changed_email(oo.email, oo)
#                         send_tg_order_status(oo, request)
#                 except Exception:
#                     pass
#             transaction.on_commit(_after_commit)

#         return HttpResponse("OK")

#     if status in ("REJECTED","CANCELED"):
#         with transaction.atomic():
#             o = Order.objects.select_for_update().get(pk=order.pk)
#             if o.status not in ("paid", "delivered", "canceled"):
#                 o.status = "created"
#                 o.save(update_fields=["status","updated"])
#         return HttpResponse("OK")

#     return HttpResponse("OK")


@csrf_exempt
@require_POST
def payment_callback(request):
    ct = request.META.get("CONTENT_TYPE", "")
    body = request.body.decode("utf-8") if request.body else ""

    try:
        data = json.loads(body) if body and "json" in ct.lower() else {}
    except json.JSONDecodeError:
        data = {}
    if not data and body:
        data = {k: v[0] for k, v in parse_qs(body).items()}

    if not data:
        return HttpResponse("BAD BODY", status=400)

    token = str(data.get("Token") or "")
    calc = tinkoff_token(data, settings.T_BANK_PASSWORD)
    if token.lower() != calc.lower():
        logger.warning("Invalid T-Bank token for order=%s", data.get("OrderId"))
        return HttpResponse("BAD TOKEN", status=400)

    order_id = str(data.get("OrderId") or "").strip()
    payment_id = str(data.get("PaymentId") or "").strip()
    status = str(data.get("Status") or "").upper()
    success = data.get("Success")
    if isinstance(success, str):
        success = success.lower() == "true"

    if (
        not order_id
        or not payment_id
        or not isinstance(success, bool)
        or not status
        or str(data.get("TerminalKey") or "") != settings.T_BANK_TERMINAL_KEY
    ):
        return HttpResponse("BAD CALLBACK", status=400)

    try:
        amount = int(data.get("Amount"))
    except (TypeError, ValueError):
        logger.warning(
            "Invalid Amount in T-Bank callback for order=%s amount=%s",
            order_id,
            data.get("Amount"),
        )
        return HttpResponse("BAD AMOUNT", status=400)

    attempt = PaymentAttempt.objects.select_related("order").filter(bank_order_id=order_id).first()
    if attempt:
        order = attempt.order
    else:
        # Backwards compatibility for payment sessions created before the
        # PaymentAttempt migration.
        try:
            order = Order.objects.get(order_id=order_id)
        except Order.DoesNotExist:
            logger.warning("T-Bank callback for unknown order %s", order_id)
            return HttpResponse("NO ORDER", status=404)
    if not order:
        logger.warning("T-Bank callback for unknown order %s", order_id)
        return HttpResponse("NO ORDER", status=404)

    expected_amount = as_kop(order.total or D("0.00"))
    if amount != expected_amount:
        logger.error(
            "T-Bank amount mismatch for order=%s expected=%s actual=%s",
            order.order_id,
            expected_amount,
            amount,
        )
        return HttpResponse("BAD AMOUNT", status=400)

    expected_payment_id = attempt.payment_id if attempt else order.payment_id
    if expected_payment_id and expected_payment_id != payment_id:
        logger.error(
            "T-Bank PaymentId mismatch for order=%s expected=%s actual=%s",
            order.order_id,
            expected_payment_id,
            payment_id,
        )
        return HttpResponse("BAD PAYMENTID", status=400)

    duplicate_payment = PaymentAttempt.objects.filter(payment_id=payment_id)
    if attempt:
        duplicate_payment = duplicate_payment.exclude(pk=attempt.pk)
    if duplicate_payment.exists() or Order.objects.filter(payment_id=payment_id).exclude(pk=order.pk).exists():
        logger.error(
            "T-Bank PaymentId %s already bound to another attempt/order for order=%s",
            payment_id,
            order.order_id,
        )
        return HttpResponse("BAD PAYMENTID", status=400)

    if success is True and status == "AUTHORIZED":
        new_status = "auth"
    elif success is True and status == "CONFIRMED":
        new_status = "paid"
    elif success is False and status in ("REJECTED", "CANCELED"):
        new_status = "declined"
    else:
        return HttpResponse("BAD STATUS", status=400)

    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order.pk)
            if attempt:
                attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt.pk)

            expected_payment_id = attempt.payment_id if attempt else order.payment_id
            if expected_payment_id and expected_payment_id != payment_id:
                logger.error(
                    "Order %s already has different payment_id %s",
                    order.order_id,
                    expected_payment_id,
                )
                return HttpResponse("BAD PAYMENTID", status=400)
            if attempt:
                attempt.payment_id = payment_id
            order.payment_id = payment_id

            if order.status == new_status:
                return HttpResponse("OK")

            if order.status not in ("created", "auth"):
                logger.warning(
                    "Ignoring payment transition %s -> %s for order=%s",
                    order.status,
                    new_status,
                    order.order_id,
                )
                return HttpResponse("OK")

            order.status = new_status
            order.save(update_fields=["status", "payment_id"])
            if attempt:
                attempt.state = new_status
                attempt.save(update_fields=["payment_id", "state", "updated"])
    except IntegrityError:
        logger.exception("PaymentId %s is already bound to another order", payment_id)
        return HttpResponse("BAD PAYMENTID", status=400)

    # The transaction has committed and released its row lock.  Only the
    # callback that changed created/auth -> paid reaches this block.
    if new_status == "paid":
        if order.ms_order_id:
            try:
                set_ms_order_state_by_uuid(
                    order.ms_order_id,
                    'db567a2a-9f5a-11ef-0a80-176f007f7c59',
                )
            except Exception:
                logger.exception("Failed to set MySklad paid state for order %s", order.order_id)

        try:
            send_tg_order_status(order, request)
        except Exception:
            logger.exception("Failed to send Telegram order status for order %s", order.order_id)

        try:
            send_order_status_changed_email(order.email, order)
        except Exception:
            logger.exception("Failed to send order status email for order %s", order.order_id)

    return HttpResponse("OK")
