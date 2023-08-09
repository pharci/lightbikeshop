from django.urls import include, re_path, path

from . import views

urlpatterns = [
	#Leave as empty string for base url
	path('cart/', views.cart, name="cart"),
	path('cart_data/', views.cart_data, name="cart_data"),
	path('checkout/', views.checkout, name="checkout"),
	path('product_edit/', views.product_edit, name="product_edit"),
	path('product_check_count/', views.product_check_count, name="product_check_count"),
	path('order_confirmed/', views.order_confirmed, name="order_confirmed"),
	path('delete_order/', views.delete_order, name="delete_order"),
]