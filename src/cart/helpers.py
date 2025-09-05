from django.http import HttpRequest, JsonResponse
from .models import Cart, SessionCart

def get_cart(request: HttpRequest):
    """Единая точка получения корзины (для анонима — SessionCart)."""
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart
    return SessionCart(request)

def json_error(msg: str, code: int = 400, **extra) -> JsonResponse:
    data = {"success": False, "error": msg}
    if extra:
        data.update(extra)
    return JsonResponse(data, status=code)