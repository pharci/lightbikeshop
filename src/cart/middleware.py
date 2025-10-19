from urllib.parse import quote
from django.shortcuts import redirect

class CheckoutGuardMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # ловим ровно /cart/checkout/ (с запасом на лишние слэши)
        path = request.path_info
        if path.startswith("/cart/checkout/"):
            # 1) требуем авторизацию
            if not request.user.is_authenticated:
                login_url = "/login/"
                return redirect(f"{login_url}?next={quote(request.get_full_path())}")

            # 2) запрещаем пустую корзину
            from cart.views.cart import get_cart  # ленивый импорт
            cart = get_cart(request)
            if not cart or (cart.get_total_items() or 0) == 0:
                return redirect("/cart/")

        return self.get_response(request)