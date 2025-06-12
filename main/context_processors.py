from cart.models import Cart

def navbar(request):
    cart_items_count = 0

    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        cart_items_count = cart.get_total_items()
    else:
        session_cart = request.session.get('cart', {})
        cart_items_count = sum(session_cart.values())

    return {'cartItems': cart_items_count}