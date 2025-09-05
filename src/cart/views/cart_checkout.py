import requests
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from ..forms import CheckoutForm
from ..models import Order, OrderItem, PromoCode
from products.models import Variant
from accounts.telegram import send_tg_order
from ..helpers import *
from .tpay import *
from .cdek import calc_cdek_pvz_price
from ..signals_copurchase_variant import bump_copurchases_variants
from ..MS import create_customer_order, set_ms_order_state_by_uuid
from ..money import iter_cart_variants, D
from django.http import HttpResponseForbidden


# ───────────────────────── pages ───────────────────────── #

def cart(request):
    cart_obj = get_cart(request)
    return render(request, "cart/cart.html", { "cart": cart_obj })

def order_detail(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)

    if request.user.is_authenticated and order.user_id == request.user.id:
        pass
    else:
        k = request.GET.get("k", "")
        if not k or k != order.access_key:
            return HttpResponseForbidden("forbidden")

    return render(request, "cart/order_detail.html", {"order": order})

@transaction.atomic
def checkout(request):
    cart = get_cart(request)

    if request.method != "POST":
        return render(request, "cart/checkout.html", {"form": CheckoutForm(), "cart": cart})

    form = CheckoutForm(request.POST)

    if not cart or (cart.get_total_items() or 0) == 0:
        messages.error(request, "Корзина пуста.")
        return render(request, "cart/checkout.html", {"form": form, "cart": cart})

    if not form.is_valid():
        for field, errs in form.errors.items():
            label = form.fields.get(field).label if field in form.fields else ""
            for e in errs:
                messages.error(request, f"{label or field}: {e}")
        for e in form.non_field_errors():
            messages.error(request, e)
        return render(request, "cart/checkout.html", {"form": form, "cart": cart})

    subtotal = D(cart.get_cart_subtotal_price() or 0)
    total_from_cart = D(cart.get_cart_total_price() or 0)
    discount = max(D("0.00"), subtotal - total_from_cart)

    delivery_method = form.cleaned_data.get("delivery_method") or ""
    pvz_code_raw = form.cleaned_data.get("pvz_code") or ""
    pvz_address  = form.cleaned_data.get("pvz_address") or ""
    city         = form.cleaned_data.get("city") or ""

    shipping_total = D("0.00")
    if delivery_method == "pickup_pvz" and pvz_code_raw.startswith("cdek:"):
        _, _, code = pvz_code_raw.partition(":")
        price, _meta = calc_cdek_pvz_price(cart, code, None)
        shipping_total = price

    lines = list(iter_cart_variants(cart))
    if not lines:
        return redirect("cart:cart")

    order = Order.objects.create(
        user=request.user if request.user.is_authenticated else None,
        user_name=form.user_name,
        contact_phone=form.cleaned_data.get("contact_phone", ""),
        email=form.cleaned_data.get("email", ""),
        order_notes=form.cleaned_data.get("order_notes") or "",
        subtotal=subtotal,
        discount_total=discount,
        shipping_total=shipping_total,
        total=subtotal - discount + shipping_total,
        payment_type="online",
        status="created",
        pvz_code=pvz_code_raw,
        pvz_address=pvz_address,
        city=city,
        promo_code=cart.get_promo_obj(),
    )

    for v, q in lines:
        OrderItem.objects.create(order=order, variant=v, price=v.price, quantity=q, amount=q * v.price)
    bump_copurchases_variants([v.id for v, q in lines for _ in range(q)])

    # создаём ссылку на оплату; корзину чистим только после успеха
    url = create_PaymentURL(order, request)
    order.payment_url = url
    order.save(update_fields=["payment_url"])

    # уведомления и интеграции не должны ломать чекаут
    try:
        send_tg_order(order, request)
    except Exception:
        pass

    try:
        ms_data = create_customer_order(order)
        if ms_data and ms_data.get("id"):
            order.ms_order_id = ms_data["id"]
            order.save(update_fields=["ms_order_id"])
    except Exception:
        # логируй по месту; чекаут не падает
        pass

    cart.clear()
    if hasattr(cart, "PROMO_KEY") and hasattr(cart, "session"):
        cart.session.pop(cart.PROMO_KEY, None)
        cart.session.modified = True

    return redirect(url)



# ───────────────────────── API for frontend ───────────────────────── #

@require_GET
def cart_data(request: HttpRequest) -> JsonResponse:
    """JSON для списка товаров в корзине."""
    cart_obj = get_cart(request)
    items_list = cart_obj.get_items()  # ожидается JSON‑friendly список
    cart_info = {
        "cart_total_price": cart_obj.get_cart_total_price(),
        "cart_subtotal_price": cart_obj.get_cart_subtotal_price(),
        "cart_total_count": cart_obj.get_total_items(),
    }
    return JsonResponse({"items": items_list, "cart": cart_info})


@require_GET
def variant_edit(request: HttpRequest) -> JsonResponse:
    vid = request.GET.get("variant_id")
    action = request.GET.get("action")  # может быть None

    if not vid:
        return JsonResponse(
            {"success": False, "error": "bad_request", "variant_id": vid, "action": action},
            status=400,
        )

    cart = get_cart(request)

    def get_variant(for_update: bool = False):
        qs = Variant.objects.select_for_update() if for_update else Variant.objects
        return get_object_or_404(qs, id=vid)

    # init-режим (без action) → просто вернуть текущее состояние
    if not action:
        v = get_variant(False)
        return JsonResponse({
            "success": True,
            "count": int(cart.get_variant_count(v) or 0),
            "stock_count": getattr(v, "inventory", None),
            "product_total_price": cart.get_variant_total_price(v) or 0,
            "cart_total_price": cart.get_cart_total_price() or 0,
            "cart_total_count": cart.get_total_items() or 0,
        })

    if action not in {"add", "remove", "remove_all"}:
        return JsonResponse(
            {"success": False, "error": "bad_request", "variant_id": vid, "action": action},
            status=400,
        )

    if action == "add":
        with transaction.atomic():
            v = get_variant(True)
            current = int(cart.get_variant_count(v) or 0)
            stock = getattr(v, "inventory", None)
            if stock is not None and current >= int(stock):
                return JsonResponse({
                    "success": False,
                    "error": "out_of_stock",
                    "count": current,
                    "stock_count": int(stock),
                    "product_total_price": cart.get_variant_total_price(v) or 0,
                    "cart_total_price": cart.get_cart_total_price() or 0,
                    "cart_total_count": cart.get_total_items() or 0,
                })
            cart.add_variant(v)

    elif action == "remove":
        v = get_variant(False)
        cart.remove_variant(v)

    else:  # remove_all
        v = get_variant(True)
        if hasattr(cart, "remove_all_variant"):
            cart.remove_all_variant(v)
        else:
            while (cart.get_variant_count(v) or 0) > 0:
                cart.remove_variant(v)

    new_count = int(cart.get_variant_count(v) or 0)
    return JsonResponse({
        "success": True,
        "count": new_count,
        "stock_count": getattr(v, "inventory", None),
        "product_total_price": cart.get_variant_total_price(v) or 0,
        "cart_total_price": cart.get_cart_total_price() or 0,
        "cart_total_count": cart.get_total_items() or 0,
    })


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


# ───────────────────────── misc ───────────────────────── #

@require_POST
def delete_order(request: HttpRequest) -> JsonResponse:
    """Отмена заказа менеджером/клиентом по номеру заказа."""
    order_id = request.POST.get("order_id")
    if not order_id:
        return json_error("missing_order_id")

    order = get_object_or_404(Order, order_id=order_id)
    order.status = "canceled"
    order.save(update_fields=["status"])

    if order.ms_order_id:
        set_ms_order_state_by_uuid(order.ms_order_id, '3f5977ad-d4a4-11ee-0a80-0cba004aacf5')

    return JsonResponse({"message": "Заказ успешно отменён."})


def order_status(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    return JsonResponse({"status": order.status})


# ──────────────────────── promo ───────────────────────── #


@require_POST
def apply_promo(request: HttpRequest):
    code = (request.POST.get("promo_code") or "").strip().upper()
    if not code:
        messages.error(request, "Введите промокод.")
        return redirect("cart:cart")

    promo = PromoCode.objects.filter(code__iexact=code, is_active=True).first()
    if not promo:
        messages.error(request, "Промокод не найден или не активен.")
        return redirect("cart:cart")

    cart = get_cart(request)
    ok, reason = cart.apply_promo(promo, user=request.user if request.user.is_authenticated else None)
    if not ok:
        messages.error(request, reason or "Промокод неприменим.")
        return redirect("cart:cart")

    messages.success(request, f"Промокод {promo.code} применён.")
    return redirect("cart:cart")

@require_POST
def remove_promo(request: HttpRequest):
    cart = get_cart(request)
    cart.remove_promo()
    messages.info(request, "Промокод удалён.")
    return redirect("cart:cart")