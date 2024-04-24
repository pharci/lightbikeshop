from django.db import models
from accounts.models import User
from store.models import ProductVariant
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import datetime

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


class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='carts', null=True, blank=True)
    session_key = models.CharField('Сессия', max_length=40, blank=True)
    promotion =  models.ForeignKey(Promotion, on_delete=models.PROTECT, null=True, blank=True)
    updated = models.DateTimeField("Последнее изменение", auto_now=True)
    created = models.DateTimeField("Дата создания", auto_now_add=True)

    def get_cart_total_price(self):
        items = self.items.all()
        price = sum([item.product_variant.price * item.count for item in items])
        return price

    def get_cart_total_count(self):
        items = self.items.all()
        count = sum([item.count for item in items])
        return count 

    class Meta:
        verbose_name = 'Корзина'
        verbose_name_plural = 'Корзины'

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    count = models.PositiveIntegerField('Количество', default=1)

    class Meta:
        verbose_name = 'Товар корзины'
        verbose_name_plural = 'Товары корзин'