from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Cart, SessionCart
from accounts.models import Order, OrderItem
from products.models import Product
from .forms import CheckoutForm
import random
from accounts.utils import send_telegram_message

def get_cart(request):
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        return cart
    else:
        return SessionCart(request)

def cart(request):
    return render(request, "cart/cart.html")

def order_confirmed(request):
    return render(request, 'cart/order_confirmed.html')

def checkout(request):
    if request.method == 'POST':
        form = CheckoutForm(request.POST)

        order_id = random.randint(10000000, 99999999)

        request.session['order_id'] = order_id
        print(form)
        if form.is_valid():
            # Получение данных из формы
            receiving_method = request.POST.get('receiving_method')
            contact_phone = request.POST.get('contact_phone')
            user_name = request.POST.get('user_name')
            pickup_location = request.POST.get('pickup_location')
            delivery_address = request.POST.get('delivery_address')
            delivery_method = request.POST.get('delivery_method')
            order_notes = request.POST.get('order_notes')
            # Создание пользователя
            if request.user.is_authenticated:
                user = request.user
                order = Order.objects.create(
                    user=user,
                    order_id=order_id,
                    user_name=user_name,
                    contact_phone=contact_phone,
                    pickup_location=pickup_location,
                    delivery_address=delivery_address,
                    delivery_method=delivery_method,
                    receiving_method=receiving_method,
                    order_notes=order_notes
                )
            else:
                order = Order.objects.create(
                    order_id=order_id,
                    user_name=user_name,
                    contact_phone=contact_phone,
                    pickup_location=pickup_location,
                    delivery_address=delivery_address,
                    delivery_method=delivery_method,
                    receiving_method=receiving_method,
                    order_notes=order_notes
                )

            order.save()

            items, cart = cartData(request)

            # Добавление товаров в заказ
            if cart:
                for item in items:
                    OrderItem.objects.create(
                        order=order,
                        product=item.product,
                        quantity=item.quantity)

                cart.clear()

            context = {'order_id': order_id}

            send_telegram_message(order, request)

            return render(request, 'cart/order_confirmed.html', context)

    else:
        form = CheckoutForm()

    cart = get_cart(request)

    context = {'form': form, 'items': cart.items(), 'cart': cart}
    return render(request, 'cart/checkout.html', context)


def cart_data(request):
    cart = get_cart(request)

    items_list = []
    for item in cart.get_items():
        product = item['product']  # обращаемся как к словарю
        quantity = item['quantity']

        items_list.append({
            'product': {
                'imageURL': product.imageURL,
                'name': product.name,
                'id': product.id
            },
            'quantity': quantity,
            'product_total_price': cart.get_product_total_price(product),
        })

    cart_info = {
        'cart_total_price': cart.get_cart_total_price(),
        'cart_total_count': cart.get_total_items()
    }

    return JsonResponse({'items': items_list, 'cart': cart_info})

def product_edit(request):
    product_id = request.GET.get('product_id')
    action = request.GET.get('action')

    if not product_id or not action:
        return JsonResponse({'success': False, 'error': 'Missing parameters'})

    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Product not found'})

    cart = get_cart(request)

    if action == 'add':
        cart.add_product(product)
    elif action == 'remove':
        cart.remove_product(product)
    else:
        return JsonResponse({'success': False, 'error': 'Invalid action'})

    count = cart.get_product_count(product)
    product_total_price = cart.get_product_total_price(product)
    cart_total_price = cart.get_cart_total_price()
    cart_total_count = cart.get_total_items()

    return JsonResponse({
        'success': True,
        'count': count,
        'product_total_price': product_total_price,
        'cart_total_price': cart_total_price,
        'cart_total_count': cart_total_count
    })


def product_check_count(request):
    product_id = request.GET.get('product_id')
    product = Product.objects.get(id=product_id)

    if product_id:

        if request.user.is_authenticated:
            cart = Cart.objects.get(user=request.user)

        else:
            cart = Cart.objects.get(id=request.session['cart_id'])


        count = cart.get_product_count(product)

        return JsonResponse({"count": count})


    return JsonResponse({'success': False})

def delete_order(request):
    # Получаем объект заказа по его идентификатору
    order_id = request.POST.get('order_id')
    order = get_object_or_404(Order, order_id=order_id)

    if request.method == 'POST':
        # Удаляем заказ
        order.status = 'canceled'
        order.save()

        # Возвращаем JSON-ответ с подтверждением удаления
        response = {
            'message': 'Заказ успешно отменён.'
        }
        return JsonResponse(response)

    # В случае GET-запроса вернем ошибку 405 Method Not Allowed
    return JsonResponse({'error': 'Метод не разрешен'}, status=405)