from django.db import models
from accounts.models import User
from store.models import ProductVariant
import uuid
import random
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import datetime
from django.utils import timezone

def generate_order_id():
    random_str = ''.join(random.choices('0123456789', k=10))
    return random_str

class OrderStatus(models.Model):
    status = models.CharField(max_length=100)
    description = models.TextField("Описание")

    def __str__(self):
        return f"{self.status}"

    class Meta:
        verbose_name = 'Статус заказа'
        verbose_name_plural = 'Статусы заказов'


class Address(models.Model):
	user = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='address', null=True, blank=True)
	address_line = models.TextField(max_length=254)
	city = models.CharField(max_length=50)
	postal_code = models.CharField(max_length=50)
	country = models.CharField(max_length=50)

	class Meta:
		verbose_name = 'Адрес'
		verbose_name_plural = 'Адреса'

class Order(models.Model):

    DELIVERY_CHOICES = (
        ('russian_post', 'Почта России'),
        ('sdek', 'Сдек'),
        ('boxberry', 'Boxberry'),
    )

    PICKUP_CHOICES = (
        ('alekseevskaya', 'Алексеевская'),
        ('colntsevo', 'Солнцево')
    )

    RECEIVING_CHOICES = (
        ('delivery', 'Доставка'),
        ('pickup', 'Самовывоз')
    )

    order_id = models.CharField('Номер заказа', max_length=10, primary_key=True, default=generate_order_id, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='orders', null=True, blank=True)
    status = models.ForeignKey(OrderStatus, on_delete=models.PROTECT, null=True, blank=True)
    username = models.CharField('ФИО', max_length=100, null=False)
    contact_phone = models.CharField('Телефон', max_length=20)
    order_notes = models.TextField('Комментарий к заказу', null=True, blank=True)
    receiving_method = models.CharField('Метод получения', max_length=50, null=True, blank=True, choices=RECEIVING_CHOICES)
    delivery_method = models.CharField('Способ доставки', max_length=50, null=True, blank=True, choices=DELIVERY_CHOICES)
    address = models.ForeignKey(Address, on_delete=models.PROTECT, null=True, blank=True)
    pickup_location = models.CharField('Пункт самовывоза', max_length=50, null=True, blank=True, choices=PICKUP_CHOICES)
    tracking_code = models.CharField('Код для отслеживания', max_length=50, null=True, blank=True)
    updated = models.DateTimeField("Последнее изменение", auto_now=True)
    created = models.DateTimeField("Дата создания", auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.pk:  # Проверка, что объект еще не сохранен (новый объект)
            while True:
                self.order_id = generate_order_id()
                if not Order.objects.filter(order_id=self.order_id).exists():
                    break
        super().save(*args, **kwargs)


    def get_total_price(self):
        orderitems = self.items.all()
        total = sum([item.count * item.product_variant.price for item in orderitems])
        return total

    def get_total_count(self):
        orderitems = self.items.all()

        total = sum([item.count for item in orderitems])
        return total 

    def __str__(self):
        return f"Заказ {self.order_id}"

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    count = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'Товар заказа'
        verbose_name_plural = 'Товары заказов'

class Promotion(models.Model):
    code = models.CharField("Промокод", max_length=50, unique=True)
    description = models.TextField("Описание", blank=True)
    discount_percentage = models.FloatField("Процент скидки", validators=[MinValueValidator(0.0), MaxValueValidator(100.0)])
    valid_from = models.DateTimeField("Действует с", default=datetime.now)
    valid_until = models.DateTimeField("Действует до", blank=True, null=True)
    active = models.BooleanField("Активная", default=True)

    def is_valid(self):
        now = timezone.now()
        if self.valid_until is None:
            return self.active and self.valid_from <= now
        return self.active and self.valid_from <= now <= self.valid_until

    def __str__(self):
        return f"{self.code} - {self.discount_percentage}%"

    class Meta:
        verbose_name = 'Акция'
        verbose_name_plural = 'Акции'