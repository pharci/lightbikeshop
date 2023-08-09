from cart.models import Cart
from products.models import Category
from django.contrib.sessions.backends.db import SessionStore
def navbar(request):
	cartItems = 0

	categories = Category.objects.exclude(slug= u'clothes').exclude(slug= u'workshop')

	# Проверяем, является ли пользователь аутентифицированным
	if request.user.is_authenticated:

		try:
			cart = Cart.objects.get(user=request.user)
			cartItems = cart.get_cart_total_count()
		except Cart.DoesNotExist:
			cart = Cart.objects.create(user=request.user)
	else:

		if 'cart_id' in request.session:

			cart_id = request.session['cart_id']
			try:
				cart = Cart.objects.get(id=cart_id)
				cartItems = cart.get_cart_total_count()

			except Cart.DoesNotExist:
				pass
		else:
			session = SessionStore()
			session.save()

			cart = Cart.objects.create(session_key=session.session_key)
			request.session['cart_id'] = cart.id

	return {'cartItems': cartItems, 'categories': categories}