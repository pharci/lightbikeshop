from .models import Cart

def cartData(request):
    if request.user.is_authenticated:
        # Для аутентифицированных пользователей создаем или получаем корзину, связанную с их аккаунтом
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        # Для неаутентифицированных пользователей используем ключ сессии
        session_key = request.session.session_key
        if not session_key:
            # Если ключ сессии еще не установлен, создаем новую сессию
            request.session.create()
            session_key = request.session.session_key

        cart, created = Cart.objects.get_or_create(session_key=session_key)

    items = cart.items.all()

    return items, cart