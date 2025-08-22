from django.http import HttpRequest, JsonResponse
from .models import Cart, SessionCart
from products.models import Variant

def get_cart(request: HttpRequest):
    """Единая точка получения корзины (для анонима — SessionCart)."""
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart
    return SessionCart(request)

def iter_cart_variants(cart):
    """
    Унифицированный итератор по (variant, qty) для БД‑корзины и сессионной корзины.
    """
    # БД‑корзина
    if hasattr(cart, "items"):
        for ci in cart.items.select_related("variant"):
            yield ci.variant, int(ci.quantity or 0)
        return
    # Сессионная корзина
    if hasattr(cart, "cart") and isinstance(cart.cart, dict):
        ids = []
        for sid in cart.cart.keys():
            try:
                ids.append(int(sid))
            except Exception:
                pass
        if not ids:
            return
        variants = {v.id: v for v in Variant.objects.filter(id__in=ids)}
        for sid, qty in cart.cart.items():
            try:
                vid = int(sid)
            except Exception:
                continue
            v = variants.get(vid)
            if v:
                yield v, int(qty or 0)

def json_error(msg: str, code: int = 400, **extra) -> JsonResponse:
    data = {"success": False, "error": msg}
    if extra:
        data.update(extra)
    return JsonResponse(data, status=code)