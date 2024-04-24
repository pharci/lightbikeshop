from django.urls import include, re_path, path

from . import views

urlpatterns = [
	path('cart/', views.cart, name="cart"),
	path('checkout/', views.checkout, name="checkout"),
	path('order_confirmed/', views.order_confirmed, name="order_confirmed"),
	path('delete_order/', views.delete_order, name="delete_order"),
	path('add_to_cart/', views.add_to_cart, name='add_to_cart'),
	path('remove_from_cart/', views.remove_from_cart, name='remove_from_cart'),
	path('delete_from_cart/', views.delete_from_cart, name='delete_from_cart'),
	path('check_item_count/', views.check_item_count, name='check_item_count'),
]