# cart/urls.py
from django.urls import path
from .views import (  # пакет views/__init__.py должен экспортировать эти вью
    cart, checkout, delete_order,
    cart_data, variant_edit, whereami,
    apply_promo, remove_promo, order_status, order_detail
)
from .views import cdek as cdek_views
from .views import tpay as tpay_views

urlpatterns = [
    # страницы
    path("cart/", cart, name="cart"),
    path("cart/checkout/", checkout, name="checkout"),

    # заказы
    path("orders/<str:order_id>/", order_detail, name="order_detail"),
    path("orders/<str:order_id>/status/", order_status, name="order_status"),

    # API: заказы
    path("api/orders/delete/", delete_order, name="order_delete"),
    path("api/payments/callback/", tpay_views.payment_callback, name="payment_callback"),

    # API: корзина
    path("api/cart/", cart_data, name="cart_data"),
    path("api/variants/", variant_edit, name="variant_update"),

    # API: промокоды
    path("api/promo/apply/", apply_promo, name="apply_promo"),
    path("api/promo/remove/", remove_promo, name="remove_promo"),

    path("api/whereami/", whereami, name="whereami"),

    path("api/pvz/shop/", cdek_views.api_shop_pvz, name="api_shop_pvz"),
    path("api/pvz/cities/", cdek_views.get_cities, name="get_cities"),
    path("api/pvz/cdek/", cdek_views.api_cdek_pvz, name="api_cdek_pvz"),
    path("api/cdek/price/", cdek_views.api_cdek_price, name="api_cdek_price"),
]
