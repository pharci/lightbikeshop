import requests, json
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import HttpRequest, JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache

from accounts.telegram import send_tg_order, send_tg_order_status
from cart.signals_copurchase_variant import bump_copurchases_variants
from cart.order_utils import iter_cart_variants, D
from cart.MS import create_customer_order, set_ms_order_state_by_uuid, _get
from cart.forms import CheckoutForm
from cart.models import Order, OrderItem

from .tpay import create_PaymentURL
from .cart import get_cart
from .cdek import calc_cdek_pvz_price
from accounts.email import send_order_created_email, send_order_status_changed_email


@require_GET
def whereami(request: HttpRequest) -> JsonResponse:
    """Геолокация → ближайший город через DaData."""
    lat = request.GET.get("lat")
    lon = request.GET.get("lon")
    if not (lat and lon):
        return JsonResponse({"city": ""})

    try:
        resp = requests.post(
            "https://suggestions.dadata.ru/suggestions/api/4_1/rs/geolocate/address",
            headers={"Authorization": f"Token {settings.DADATA_TOKEN}"},
            json={"lat": float(lat), "lon": float(lon), "count": 1},
            timeout=5,
        )
        city = ""
        if resp.ok:
            data = resp.json()
            s0 = (data.get("suggestions") or [{}])[0]
            d = s0.get("data", {})
            city = d.get("city") or d.get("settlement") or ""
        return JsonResponse({"city": city})
    except Exception:
        return JsonResponse({"city": ""})

def order_detail(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)

    if request.user.is_authenticated and order.user_id == request.user.id:
        pass
    else:
        k = request.GET.get("k", "")
        if not k or k != order.access_key:
            return HttpResponseForbidden("forbidden")

    return render(request, "cart/order_detail.html", {"order": order})


@require_POST
def delete_order(request: HttpRequest) -> JsonResponse:
    """Отмена заказа менеджером/клиентом по номеру заказа."""
    order_id = request.POST.get("order_id")
    if not order_id:
        return JsonResponse({"message": "Заказ не найден."})

    order = get_object_or_404(Order, order_id=order_id)
    order.status = "canceled"
    order.save(update_fields=["status"])

    if order.ms_order_id:
        set_ms_order_state_by_uuid(order.ms_order_id, '3f5977ad-d4a4-11ee-0a80-0cba004aacf5')

    return JsonResponse({"message": "Заказ успешно отменён."})


def order_status(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    return JsonResponse({"status": order.status})

@never_cache
@transaction.atomic
def checkout(request):
    cart = get_cart(request)

    if request.method != "POST":
        return render(request, "cart/checkout.html", {"form": CheckoutForm(), "cart": cart})

    form = CheckoutForm(request.POST)

    if not cart or (cart.get_total_items() or 0) == 0:
        messages.error(request, "Корзина пуста.", extra_tags="global")
        return render(request, "cart/checkout.html", {"form": form, "cart": cart})

    if cart.get_cart_total_price() <= 1:
        messages.error(request, "Сумма заказа должна быть больше 1 рубля.", extra_tags="global")
        return render(request, "cart/checkout.html", {"form": form, "cart": cart})

    # валидация формы: НИЧЕГО не пишем в messages для field-ошибок
    if not form.is_valid():
        # если хочешь, подними именно non_field_errors в messages-глобальные:
        for e in form.non_field_errors():
            messages.error(request, e, extra_tags="global")
        return render(request, "cart/checkout.html", {"form": form, "cart": cart})

    subtotal = D(cart.get_cart_subtotal_price() or 0)
    total_from_cart = D(cart.get_cart_total_price() or 0)
    discount = max(D("0.00"), subtotal - total_from_cart)

    delivery_method = form.cleaned_data.get("delivery_method") or ""
    pvz_provider = form.cleaned_data.get("pvz_provider") or ""
    pvz_code = form.cleaned_data.get("pvz_code") or ""
    pvz_address  = form.cleaned_data.get("pvz_address") or ""
    city         = form.cleaned_data.get("city") or ""

    shipping_total = D("0.00")
    if delivery_method == "pickup_pvz" and pvz_provider == "cdek":
        price, _meta = calc_cdek_pvz_price(cart, pvz_code, None)
        shipping_total = price

    lines = list(iter_cart_variants(cart))
    if not lines:
        return redirect("cart:cart")
    
    email = request.user.email if request.user.is_authenticated else None

    order = Order.objects.create(
        user=request.user if request.user.is_authenticated else None,
        user_name=form.user_name,
        contact_phone=form.cleaned_data.get("contact_phone", ""),
        email=email,
        order_notes=form.cleaned_data.get("order_notes") or "",
        subtotal=subtotal,
        discount_total=discount,
        shipping_total=shipping_total,
        total=subtotal - discount + shipping_total,
        payment_type="online",
        status="created",
        pvz_provider=pvz_provider,
        pvz_code=pvz_code,
        pvz_address=pvz_address,
        city=city,
        promo_code=cart.get_promo_obj(),
    )

    for v, q in lines:
        OrderItem.objects.create(order=order, variant=v, price=v.price, quantity=q, amount=q * v.price)
    bump_copurchases_variants([v.id for v, q in lines for _ in range(q)])

    url = create_PaymentURL(order, request)
    order.payment_url = url
    order.save(update_fields=["payment_url"])

    try:
        ms_data = create_customer_order(order)
        if ms_data and ms_data.get("id"):
            order.ms_order_id = ms_data["id"]
            order.save(update_fields=["ms_order_id"])
    except Exception as e:
        print(e)

    try:
        send_tg_order(order, request)
    except Exception as e:
        print(e)

    try:
        send_order_created_email(email, order)
    except Exception as e:
        print(e)

    cart.clear()
    if hasattr(cart, "PROMO_KEY") and hasattr(cart, "session"):
        cart.session.pop(cart.PROMO_KEY, None)
        cart.session.modified = True

    return redirect(url)

MS_STATUS_MAP = {
    "3f597230-d4a4-11ee-0a80-0cba004aacef": "created",        # Новый
    "3f597379-d4a4-11ee-0a80-0cba004aacf0": "confirmed",      # Подтвержден
    "3f5973f2-d4a4-11ee-0a80-0cba004aacf1": "assembled",      # Собран
    "e150a7d1-a7f4-11ef-0a80-151c00235a78": "pickup",         # Самовывоз
    "3f597466-d4a4-11ee-0a80-0cba004aacf2": "shipped",        # Отгружен
    "3f5974d9-d4a4-11ee-0a80-0cba004aacf3": "delivered",      # Доставлен
    "3f59753a-d4a4-11ee-0a80-0cba004aacf4": "returned",       # Возврат
    "3f5977ad-d4a4-11ee-0a80-0cba004aacf5": "canceled",       # Отменен
    "db5148c9-9f5a-11ef-0a80-176f007f7c56": "auth",           # Платеж авторизован
    "db567a2a-9f5a-11ef-0a80-176f007f7c59": "paid",           # Оплачен
    "db582415-9f5a-11ef-0a80-176f007f7c5b": "declined",       # Отклонен
    "db5a8b19-9f5a-11ef-0a80-176f007f7c5e": "partial_return", # Частичный возврат
}

@csrf_exempt
def ms_order_webhook(request):
    try:
        events = (json.loads(request.body.decode("utf-8") or "{}").get("events")) or []
    except Exception:
        return JsonResponse({"ok": True}, status=200)

    for ev in events:
        href = (ev or {}).get("meta", {}).get("href")
        if not href:
            continue
        try:
            d = _get(href)
        except Exception:
            continue
        if (d.get("meta") or {}).get("type") != "customerorder":
            continue

        ms_id = d.get("id")
        if not ms_id:
            continue

        state_href = ((d.get("state") or {}).get("meta") or {}).get("href") or ""
        state_id = state_href.rsplit("/", 1)[-1] if state_href else None
        new_status = MS_STATUS_MAP.get(state_id)

        invoice = None
        for a in d.get("attributes") or []:
            if a.get("id") == "4e9549ae-66ac-11ef-0a80-05be0019d751" or a.get("name") == "Накладная СДЭК":
                invoice = a.get("value")
                break

        if new_status:
            rows = Order.objects.filter(ms_order_id=ms_id).exclude(status=new_status).update(status=new_status)
            if rows:
                try:
                    order = Order.objects.get(ms_order_id=ms_id)
                    send_tg_order_status(order, request)
                    send_order_status_changed_email(order.email, order)
                except Exception:
                    pass

        if invoice is not None:
            Order.objects.filter(ms_order_id=ms_id).exclude(invoice=invoice).update(invoice=invoice)

    return JsonResponse({"ok": True}, status=200)