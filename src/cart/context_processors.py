from .views.cart import get_cart

def cartCount(request):
    cart = get_cart(request)
    return {"cartItems": cart.get_total_items()}