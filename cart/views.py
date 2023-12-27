from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
import json
import datetime
from django.db.models import Q
from .models import Cart, CartItem
from accounts.models import Order, OrderItem, User
from products.models import Product
from .forms import CheckoutForm
import uuid
import random
import string
from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime
from .utils import cartData
from django.core import serializers
import random
from accounts.utils import send_telegram_message
from django.http import JsonResponse
from django.views.decorators.http import require_POST

def create_cart(user):
    try:
        Cart.objects.get(user=user)
    except Cart.DoesNotExist:
        Cart.objects.create(user=user)

def cart(request):

    items, cart = cartData(request)

    for item in items:
        item.total = item.product.price * item.quantity

    cart.quantity = cart.get_cart_total_count()
    cart.total = cart.get_cart_total_price()

    context = {'items': items, 'cart': cart}

    return render(request, "cart/cart.html", context)

@require_POST
def add_to_cart(request, product_id):

    items, cart = cartData(request)

    product = get_object_or_404(Product, pk=product_id)

    cart_item, item_created = CartItem.objects.get_or_create(cart=cart, product=product)

    item_quantity = cart_item.quantity + 1
    item_total_price = item_quantity * product.price

    cart_item.quantity += 1
    cart_item.save()

    response_data = {
        'cart_total_price': cart.get_cart_total_price(),
        'cart_total_count': cart.get_cart_total_count(),
        'item_quantity': item_quantity,
        'item_total_price': item_total_price,
    }

    return JsonResponse(response_data)


@require_POST
def remove_from_cart(request, product_id):

    items, cart = cartData(request)

    product = get_object_or_404(Product, pk=product_id)

    cart_item, item_created = CartItem.objects.get_or_create(cart=cart, product=product)

    item_quantity = cart_item.quantity + 1
    item_total_price = item_quantity * product.price

    cart_item.quantity -= 1
    cart_item.save()

    response_data = {
        'cart_total_price': cart.get_cart_total_price(),
        'cart_total_count': cart.get_cart_total_count(),
        'item_quantity': item_quantity,
        'item_total_price': item_total_price,
    }

    return JsonResponse(response_data)


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

    items, cart = cartData(request)

    context = {'form': form, 'items': items, 'cart': cart}
    return render(request, 'cart/checkout.html', context)

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