# cart/middleware.py
from django.shortcuts import redirect
from django.urls import reverse
from .helpers import get_cart

class CheckoutCartGuardMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if path.startswith(reverse("cart:checkout")):
            cart = get_cart(request)
            if not cart or (cart.get_total_items() or 0) == 0:
                return redirect("cart:cart")  # имя url корзины

        return self.get_response(request)