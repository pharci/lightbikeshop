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

def create_cart(user):
    try:
        Cart.objects.get(user=user)
    except Cart.DoesNotExist:
        Cart.objects.create(user=user)

def cart(request):
    return render(request, "cart/cart.html")

def order_confirmed(request):

    return render(request, 'cart/order_confirmed.html')

def checkout(request):
    if request.method == 'POST':
        form = CheckoutForm(request.POST)

        order_id = random.randint(10000000, 99999999)

        request.session['order_id'] = order_id

        if form.is_valid():
            # Получение данных из формы
            last_name = form.cleaned_data['last_name']
            first_name = form.cleaned_data['first_name']
            middle_name = form.cleaned_data['middle_name']
            phone_number = form.cleaned_data['phone_number']
            address = form.cleaned_data['address']
            city = form.cleaned_data['city']
            zip_code = form.cleaned_data['zip_code']
            delivery_value = form.cleaned_data['delivery_value']
            # Создание пользователя
            if request.user.is_authenticated:
                user = request.user
                order = Order.objects.create(
                    user=user,
                    order_id=order_id,
                    first_name=first_name,
                    last_name=last_name,
                    middle_name=middle_name,
                    phone_number=phone_number,
                    address=address,
                    zip_code=zip_code,
                    city=city,
                    delivery_value=delivery_value
                )
            else:
                order = Order.objects.create(
                    order_id=order_id,
                    first_name=first_name,
                    last_name=last_name,
                    middle_name=middle_name,
                    phone_number=phone_number,
                    address=address,
                    zip_code=zip_code,
                    city=city,
                    delivery_value=delivery_value
                )

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

        return render(request, 'cart/order_confirmed.html', context)

    else:
        form = CheckoutForm()

    items, cart = cartData(request)

    context = {'form': form, 'items': items, 'cart': cart}
    return render(request, 'cart/checkout.html', context)


def cart_data(request):
    items, cart = cartData(request)
    items_list = []
    for item in items:
        items_list.append({
            'product': {
                'imageURL': item.product.imageURL,
                'name': item.product.name,
                'id': item.product.id
            },
            'quantity': item.quantity,
            'stock_count': item.product.count,
            'product_total_price': cart.get_product_total_price(item.product),
        })

    cart = {'cart_total_price': cart.get_cart_total_price(), 'cart_total_count': cart.get_cart_total_count()}

    return JsonResponse({'items': items_list, 'cart': cart})

def product_edit(request):
    product_id = request.GET.get('product_id')
    action = request.GET.get('action')

    product = Product.objects.get(id=product_id)
    stock_count = product.count

    if product_id:

        if request.user.is_authenticated:
                cart = Cart.objects.get(user=request.user)

        else:
            cart_id = request.session['cart_id']
            cart = Cart.objects.get(id=cart_id)

        count = cart.get_product_count(product)

        if action == 'add' and count < stock_count:
            cart.add_product(product)

        elif action == 'remove':
            cart.remove_product(product)

        count = cart.get_product_count(product)
        product_total_price = cart.get_product_total_price(product)

        cart_total_price = cart.get_cart_total_price()
        cart_total_count = cart.get_cart_total_count()

        return JsonResponse({'cart_total_price': cart_total_price, 'cart_total_count': cart_total_count, "count": count, 'stock_count': stock_count, 'product_total_price': product_total_price})


    return JsonResponse({'success': False})

def product_check_count(request):
    product_id = request.GET.get('product_id')
    product = Product.objects.get(id=product_id)

    if product_id:

        if request.user.is_authenticated:
            cart = Cart.objects.get(user=request.user)

        else:
            cart = Cart.objects.get(id=request.session['cart_id'])


        count = cart.get_product_count(product)

        return JsonResponse({"count": count, 'stock_count': product.count})


    return JsonResponse({'success': False})

def delete_order(request):
    # Получаем объект заказа по его идентификатору
    order_id = request.POST.get('order_id')
    order = get_object_or_404(Order, order_id=order_id)

    if request.method == 'POST':
        # Удаляем заказ
        order.status = 'Отменен'
        order.save()

        # Возвращаем JSON-ответ с подтверждением удаления
        response = {
            'message': 'Заказ успешно отменён.'
        }
        return JsonResponse(response)

    # В случае GET-запроса вернем ошибку 405 Method Not Allowed
    return JsonResponse({'error': 'Метод не разрешен'}, status=405)