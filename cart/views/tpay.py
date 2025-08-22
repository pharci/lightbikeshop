# views.py
import requests
from django.conf import settings
import json, hashlib
from django.http import HttpResponse, JsonResponse
from ..models import Order
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from urllib.parse import parse_qs
from decimal import Decimal, ROUND_HALF_UP

def kops(x: Decimal) -> int:
    return int((x.quantize(Decimal("0.01"), ROUND_HALF_UP) * 100).to_integral_value())

def build_receipt(order):
    items = []
    for it in order.items.all():  # адаптируй доступ
        name = (it.variant.display_name())[:128]
        price = Decimal(it.price)           # за 1 шт, ₽
        qty = Decimal(it.quantity)
        amount = price * qty                # ₽

        items.append({
            "Name": name,
            "Price": kops(price),           # копейки
            "Quantity": float(qty),         # число
            "Amount": kops(amount),         # копейки
            "Tax": "none",                  # или "vat20"/"vat10"/"vat0"
            "PaymentMethod": "full_prepayment",  # рекомендовано
            "PaymentObject": "commodity",        # товар/услуга и т.д.
        })

    total = sum(i["Amount"] for i in items)
    assert total == kops(order.amount), "Сумма позиций не равна Amount"
    receipt = {
        "Email": order.email,
        "Phone": order.contact_phone,               
        "Taxation": "usn_income",
        "Items": items,
        "CompanyEmail": "lightbikeshop@yandex.ru",    
    }
    return receipt

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

def create_PaymentURL(order):
    url = "https://securepay.tinkoff.ru/v2/Init"
    payload = {
        "TerminalKey": settings.T_BANK_TERMINAL_KEY,
        "OrderId": str(order.order_id),
        "Amount": int(order.amount * 100),
        "SuccessURL": f"https://pharci.ru/orders/{order.order_id}/",
        "FailURL": f"https://pharci.ru/orders/{order.order_id}/",
        "NotificationURL": "https://pharci.ru/api/payment_callback/",
        "Receipt": build_receipt(order),
    }
    payload["Token"] = tinkoff_token(payload, settings.T_BANK_PASSWORD)  # секрет из ЛК

    r = requests.post(url, json=payload, timeout=15)
    data = r.json()
    if not data.get("Success"):
        raise Exception(f"Init error: {data}")
    return data["PaymentURL"]

def order_detail(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    return render(request, "cart/order_detail.html", {"order": order})

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
    elif status in ("REJECTED", "CANCELED"):
        order.status = "created"  # или сразу canceled, если хочешь
    order.save(update_fields=["status"])

    return HttpResponse("OK")