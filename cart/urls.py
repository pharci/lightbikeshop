# cart/urls.py
from django.urls import path
from .views import (  # пакет views/__init__.py должен экспортировать эти вью
    cart, checkout, delete_order,
    cart_data, variant_edit, variant_check_count,
    pickup_points, city_suggest, whereami,
    apply_promo, remove_promo, order_pay, order_status
)
from .views import cdek as cdek_views
from .views import tpay as tpay_views

urlpatterns = [
    # Pages
    path("cart/", cart, name="cart"),
    path("checkout/", checkout, name="checkout"),

    path("orders/<str:order_id>/", tpay_views.order_detail, name="order_detail"),
    path("orders/<str:order_id>/pay/", order_pay, name="order_pay"),
    path("api/payment_callback/", tpay_views.payment_callback, name="payment_callback"),
    path("api/<str:order_id>/status", order_status, name="order_status"),
    
    path("delete_order/", delete_order, name="delete_order"),

    # API (frontend)
    path("cart_data/", cart_data, name="cart_data"),
    path("variant_edit/", variant_edit, name="variant_edit"),
    path("variant_check_count/", variant_check_count, name="variant_check_count"),
    path("api/pickup-points/", pickup_points, name="pickup_points"),
    path("api/city-suggest/", city_suggest, name="city_suggest"),
    path("api/whereami", whereami, name="whereami"),
    path("promo/apply/", apply_promo, name="apply_promo"),
    path("promo/remove/", remove_promo, name="remove_promo"),
    # CDEK proxy
    path("api/cdek-service/", cdek_views.cdek_service, name="cdek_service"),
]