from .utils import cartData
from django.shortcuts import redirect
from django.urls import reverse

class CartValidationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == reverse('cart:checkout'):
            # Проверка корзины на наличие недействительных товаров и пустоту
            items, cart = cartData(request)
            invalid_items = []

            for item in items:
                quantity_in_cart = item.quantity
                quantity_in_stock = item.product.count

                if quantity_in_cart > quantity_in_stock:
                    # Добавить недействительный товар в список
                    invalid_items.append(item)

            if invalid_items or not items:
                # Если есть недействительные товары или корзина пуста, перенаправить на страницу корзины
                return redirect('cart:cart')
                
        response = self.get_response(request)
        return response
