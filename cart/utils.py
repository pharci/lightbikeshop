from .models import Cart

def cartData(request):
    if request.user.is_authenticated:

        cart = Cart.objects.get(user=request.user)

    else:
        
        session_key = request.session.session_key

        if not session_key:
            request.session.create()
            session_key = request.session.session_key

        cart, created = Cart.objects.get_or_create(session_key=session_key)

    items = cart.items.all()

    return items, cart