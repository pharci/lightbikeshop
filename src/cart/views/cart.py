from django.contrib import messages
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
from django.http import HttpRequest, JsonResponse

from cart.models import Cart, SessionCart, PromoCode
from products.models import Variant

def get_cart(request: HttpRequest):
    """Единая точка получения корзины (для анонима — SessionCart)."""
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart
    return SessionCart(request)

def cart(request):
    cart_obj = get_cart(request)
    return render(request, "cart/cart.html", { "cart": cart_obj })

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
    action = request.GET.get("action")

    if not vid:
        return JsonResponse({"success": False, "error": "bad_request", "variant_id": vid, "action": action}, status=400)

    cart = get_cart(request)

    def get_variant(for_update: bool = False):
        qs = Variant.objects.select_for_update() if for_update else Variant.objects
        return get_object_or_404(qs, id=vid)

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
        return JsonResponse({"success": False, "error": "bad_request", "variant_id": vid, "action": action}, status=400)

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
        with transaction.atomic():
            v = get_variant(True)
            if hasattr(cart, "remove_all_variant"):
                cart.remove_all_variant(v)
            else:
                cnt = int(cart.get_variant_count(v) or 0)
                for _ in range(cnt):
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