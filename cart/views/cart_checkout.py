from typing import Optional
from decimal import Decimal

import requests
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from ..forms import CheckoutForm
from ..models import Order, OrderItem, PickupPoint, PromoCode
from products.models import Variant
from accounts.telegram import send_tg_order
from ..models import gen_order_code
from ..helpers import *
from .tpay import *


# ───────────────────────── pages ───────────────────────── #

def cart(request):
    cart_obj = get_cart(request)
    promo_obj = cart_obj._get_promo_obj()
    if promo_obj:
        return render(request, "cart/cart.html", {
        "cart": cart_obj,
        "applied_promo_code": promo_obj,
    })

    return render(request, "cart/cart.html", { "cart": cart_obj })

@transaction.atomic
def checkout(request):
    cart = get_cart(request)
    if request.method != "POST":
        return render(request, "cart/checkout.html", {"form": CheckoutForm(), "cart": cart})

    form = CheckoutForm(request.POST)
    if not cart or (cart.get_total_items() or 0) == 0 or not form.is_valid():
        return render(request, "cart/checkout.html", {"form": form, "cart": cart})

    subtotal = cart.get_cart_subtotal_price()
    total = cart.get_cart_total_price()
    discount = max(Decimal("0.00"), subtotal - total)

    order = Order.objects.create(
        user=request.user if request.user.is_authenticated else None,
        order_id=gen_order_code(14),
        user_name=form.user_name,
        contact_phone=form.cleaned_data.get("contact_phone", ""),
        email=form.cleaned_data.get("email", ""),
        order_notes=form.cleaned_data.get("order_notes") or "",
        amount=total, payment_type="online", status="created",
        city=form.cleaned_data.get("city") or "",
        pvz_code=form.cleaned_data.get("pvz_code") or "",
        pvz_address=form.cleaned_data.get("pvz_address") or "",
        promo_discount_amount=discount,
    )

    ratio = (total / subtotal) if subtotal > 0 else Decimal("1.00")
    draft = []
    for v, qty in iter_cart_variants(cart):
        if not v or qty <= 0: continue
        p = (Decimal(v.price) * ratio).quantize(Decimal("0.01"))
        draft.append({"v": v, "q": int(qty), "p": p})
    if not draft: return redirect("cart:cart")

    sum_rub = sum(d["p"] * d["q"] for d in draft)
    diff_k = int(((total - sum_rub) * 100).to_integral_value())
    if diff_k:
        idx = [i for i in range(len(draft)) if draft[i]["q"] == 1] + [i for i in range(len(draft)) if draft[i]["q"] != 1]
        step = Decimal("0.01") * (1 if diff_k > 0 else -1)
        for i in range(abs(diff_k)):
            draft[idx[i % len(idx)]]["p"] = (draft[idx[i % len(idx)]]["p"] + step).quantize(Decimal("0.01"))

    for d in draft:
        OrderItem.objects.create(order=order, variant=d["v"], price=d["p"], quantity=d["q"])

    print("Send Tg")
    send_tg_order(order, request)

    # try: cart.clear()
    # finally:
    #     if hasattr(cart, "PROMO_KEY") and hasattr(cart, "session"):
    #         cart.session.pop(cart.PROMO_KEY, None); cart.session.modified = True

    return redirect(create_PaymentURL(order))


def order_pay(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    return redirect(create_PaymentURL(order))


# ───────────────────────── API for frontend ───────────────────────── #

@require_GET
def cart_data(request: HttpRequest) -> JsonResponse:
    """JSON для списка товаров в корзине."""
    cart_obj = get_cart(request)
    items_list = cart_obj.get_items()  # ожидается JSON‑friendly список
    cart_info = {
        "cart_total_price": cart_obj.get_cart_total_price(),
        "cart_total_count": cart_obj.get_total_items(),
    }
    return JsonResponse({"items": items_list, "cart": cart_info})


@require_GET
def variant_edit(request: HttpRequest) -> JsonResponse:
    """
    Изменить количество варианта в корзине (add/remove/remove_all).
    Обновлённые суммы возвращаем сразу.
    """
    variant_id = request.GET.get("variant_id")
    action = request.GET.get("action")

    if not variant_id or action not in ("add", "remove", "remove_all"):
        return json_error("bad_request", variant_id=variant_id, action=action)

    # Для БД‑корзины берём блокировку строки варианта
    qs = Variant.objects.select_for_update(of=("self",)) if request.user.is_authenticated else Variant.objects
    variant = get_object_or_404(qs, id=variant_id)

    cart_obj = get_cart(request)

    # Унифицируем названия методов под разные реализации корзины
    add_fn = getattr(cart_obj, "add_variant", getattr(cart_obj, "add_product", None))
    rm_fn = getattr(cart_obj, "remove_variant", getattr(cart_obj, "remove_product", None))
    rm_all_fn = getattr(cart_obj, "remove_all_variant", getattr(cart_obj, "remove_all_product", None))
    cnt_fn = getattr(cart_obj, "get_variant_count", getattr(cart_obj, "get_product_count", None))
    line_total_fn = getattr(cart_obj, "get_variant_total_price", getattr(cart_obj, "get_variant_total_price", None))
    cart_total_fn = getattr(cart_obj, "get_cart_total_price")

    if not all([add_fn, rm_fn, cnt_fn, line_total_fn, cart_total_fn]):
        return json_error("cart_methods_missing")

    current = int(cnt_fn(variant) or 0)
    stock: Optional[int] = getattr(variant, "inventory", None)

    if action == "add":
        if stock is not None and current >= stock:
            return JsonResponse({
                "success": False,
                "error": "out_of_stock",
                "count": current,
                "stock_count": stock,
                "product_total_price": line_total_fn(variant) or 0,
                "cart_total_price": cart_total_fn(),
                "cart_total_count": cart_obj.get_total_items(),
            })
        with transaction.atomic():
            add_fn(variant)

    elif action == "remove":
        rm_fn(variant)

    elif action == "remove_all":
        if callable(rm_all_fn):
            rm_all_fn(variant)
        else:
            while (cnt_fn(variant) or 0) > 0:
                rm_fn(variant)

    new_count = int(cnt_fn(variant) or 0)
    return JsonResponse({
        "success": True,
        "count": new_count,
        "stock_count": stock,
        "product_total_price": line_total_fn(variant) or 0,
        "cart_total_price": cart_total_fn(),
        "cart_total_count": cart_obj.get_total_items(),
    })


@require_GET
def variant_check_count(request: HttpRequest) -> JsonResponse:
    """Текущие количество варианта в корзине + запас на складе."""
    variant_id = request.GET.get("variant_id")
    if not variant_id:
        return json_error("missing_variant_id")

    variant = get_object_or_404(Variant, id=variant_id)
    cart_obj = get_cart(request)

    cnt_fn = getattr(cart_obj, "get_variant_count", getattr(cart_obj, "get_product_count", None))
    count = int(cnt_fn(variant) or 0) if cnt_fn else 0

    return JsonResponse({
        "success": True,
        "count": count,
        "stock_count": getattr(variant, "inventory", None),
    })


@require_GET
def pickup_points(request: HttpRequest) -> JsonResponse:
    """Наши собственные пункты самовывоза (не СДЭК)."""
    qcity = (request.GET.get("city") or "").strip()
    qs = PickupPoint.objects.filter(is_active=True)
    if qcity:
        qs = qs.filter(city__iexact=qcity)
    data = [{
        "id": p.id,
        "slug": p.slug,
        "title": p.title,
        "city": p.city,
        "address": p.address,
        "lat": p.lat, "lon": p.lon,
        "schedule": p.schedule,
    } for p in qs]
    return JsonResponse({"items": data})


@require_GET
def city_suggest(request: HttpRequest) -> JsonResponse:
    """Подсказки городов через DaData (только города/посёлки)."""
    q = (request.GET.get("q") or "").strip()
    if not q:
        return JsonResponse({"items": []})

    try:
        resp = requests.post(
            "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address",
            headers={
                "Authorization": f"Token {settings.DADATA_TOKEN}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "query": q,
                "count": 7,
                "from_bound": {"value": "city"},
                "to_bound": {"value": "settlement"},
            },
            timeout=5,
        )
        items = []
        if resp.ok:
            for s in resp.json().get("suggestions", []):
                d = s.get("data", {})
                name = d.get("city") or d.get("settlement") or s.get("value")
                if not name:
                    continue
                items.append({
                    "name": name,
                    "region": d.get("region"),
                    "lat": d.get("geo_lat"),
                    "lon": d.get("geo_lon"),
                })
        return JsonResponse({"items": items})
    except Exception:
        # на фейле — пусто (чтобы фронт не падал)
        return JsonResponse({"items": []})


@require_GET
def whereami(request: HttpRequest) -> JsonResponse:
    """Геолокация → ближайший город через DaData."""
    lat = request.GET.get("lat")
    lon = request.GET.get("lon")
    print(1)
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