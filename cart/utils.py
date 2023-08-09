from .models import Cart

def cartData(request):
    if request.user.is_authenticated:

        cart = Cart.objects.get(user=request.user)

    else:
        
        cart_id = request.session['cart_id']

        cart = Cart.objects.get(id=cart_id)

    items = cart.items.all()

    return items, cart