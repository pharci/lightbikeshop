from .models import Cart

def cart_context(request):
    cart = Cart.get_cart(request)
    cart_items_count = cart.get_cart_total_count() if cart else 0
    return {
        'cart': cart,
        'cart_items_count': cart_items_count
    }