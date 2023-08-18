from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
import random
import requests
from django.urls import reverse
from django.contrib.sites.shortcuts import get_current_site

def generate_verification_code():
    return str(random.randint(100000, 999999))

def send_verification_code(email, code):
    subject = 'Проверочный код'
    message = f'Ваш проверочный код: {code}.'
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [email]
    
    send_mail(subject, message, from_email, recipient_list)

def send_telegram_message(order, request):
    domain = get_current_site(request).domain
    link = reverse("admin:accounts_order_change", args=[order.id])
    order_link = f"http://{domain}{link}"

    message = f"*Заказ №{order.order_id}* - "
    message += f"[Ссылка на заказ]({order_link})\n\n"
    message += f"*Статус*: {order.get_status_display()}\n\n"
    message += f"*Имя*: {order.user_name}\n"
    message += f"*Телефон*: {order.contact_phone}\n"
    message += f"*Комментарий к заказу*: {order.order_notes}\n\n"

    if order.receiving_method == 'pickup':
        message += f"*Метод получения*: Самовывоз\n"
        message += f"*Пункт самовывоза*: {order.get_pickup_location_display()}\n"
    else:
        message += f"*Метод получения*: Доставка\n"
        message += f"*Адрес*: {order.delivery_address}\n"
        message += f"*Способ доставки*: {order.get_delivery_method_display()}\n"


    message += "\n*Товары*:\n"
    for item in order.items.all():
        message += f"{item.product.name} - {item.quantity} шт. x {item.product.price} руб.\n"



    message += f"\n*Итого товаров*: {order.get_total_count()} шт.\n"
    message += f"*Общая стоимость*: {order.get_total_price()} руб.\n"

    chat_id = ['787640915']

    response = requests.get(f'https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage?chat_id={787640915}&parse_mode=Markdown&text={message}')

    return message