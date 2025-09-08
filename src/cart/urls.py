# cart/urls.py
from django.urls import path

from .views.cdek import *
from .views.tpay import *
from .views.cart import *
from .views.order import *

urlpatterns = [
    # страницы
    path("cart/", cart, name="cart"),
    path("cart/checkout/", checkout, name="checkout"),

    # заказы
    path("orders/<str:order_id>/", order_detail, name="order_detail"),
    path("orders/<str:order_id>/status/", order_status, name="order_status"),

    # API: заказы
    path("api/orders/delete/", delete_order, name="order_delete"),
    path("api/payments/callback/", payment_callback, name="payment_callback"),

    # API: корзина
    path("api/cart/", cart_data, name="cart_data"),
    path("api/variants/", variant_edit, name="variant_update"),

    # API: промокоды
    path("api/promo/apply/", apply_promo, name="apply_promo"),
    path("api/promo/remove/", remove_promo, name="remove_promo"),

    path("api/whereami/", whereami, name="whereami"),

    path("api/pvz/shop/", api_shop_pvz, name="api_shop_pvz"),
    path("api/pvz/cities/", get_cities, name="get_cities"),
    path("api/pvz/cdek/", api_cdek_pvz, name="api_cdek_pvz"),
    path("api/cdek/price/", api_cdek_price, name="api_cdek_price"),

    path("ms/webhooks/order", ms_order_webhook),
]
