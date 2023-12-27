from django.urls import include, re_path, path

from . import views

urlpatterns = [
	#Leave as empty string for base url
	path('cart/', views.cart, name="cart"),
	path('checkout/', views.checkout, name="checkout"),
	path('order_confirmed/', views.order_confirmed, name="order_confirmed"),
	path('delete_order/', views.delete_order, name="delete_order"),
	path('add_to_cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
	path('remove_from_cart/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
]