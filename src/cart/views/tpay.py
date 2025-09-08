# views.py
import requests, json, hashlib
from urllib.parse import parse_qs

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from cart.models import Order
from cart.MS import set_ms_order_state_by_uuid
from cart.order_utils import as_kop, D, allocate_lines
from cart.order_utils import as_kop, D, allocate_lines
from accounts.telegram import send_tg_order_status

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

def create_PaymentURL(order, request):
    url = "https://securepay.tinkoff.ru/v2/Init"
    payload = {
        "TerminalKey": settings.T_BANK_TERMINAL_KEY,
        "OrderId": str(order.order_id),
        "Amount": int(D(order.total or 0) * 100),  # копейки с нового поля total
        "SuccessURL": request.build_absolute_uri(order.get_absolute_url()),
        "FailURL": request.build_absolute_uri(order.get_absolute_url()),
        "NotificationURL": request.build_absolute_uri("/api/payments/callback/"),
        "Receipt": build_receipt(order),
    }
    payload["Token"] = tinkoff_token(payload, settings.T_BANK_PASSWORD)

    r = requests.post(url, json=payload, timeout=15)
    data = r.json()
    if not data.get("Success"):
        raise Exception(f"Init error: {data}")
    return data["PaymentURL"]

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
        return HttpResponse("BAD TOKEN", status=400)

    order_id = data.get("OrderId")
    status = str(data.get("Status") or "").upper()
    success = data.get("Success")
    if isinstance(success, str):
        success = success.lower() == "true"

    try:
        order = Order.objects.get(order_id=order_id)
    except Order.DoesNotExist:
        return HttpResponse("NO ORDER", status=404)

    if success and status in ("CONFIRMED", "AUTHORIZED"):
        order.status = "paid"
        try:
            set_ms_order_state_by_uuid(order.ms_order_id, 'db567a2a-9f5a-11ef-0a80-176f007f7c59')
            send_tg_order_status(order, request)
        except:
            pass
        
    elif status in ("REJECTED", "CANCELED"):
        order.status = "created"  # или сразу canceled, если хочешь
    order.save(update_fields=["status"])

    return HttpResponse("OK")