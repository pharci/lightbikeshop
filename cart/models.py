from django.db import models
from accounts.models import User
from store.models import ProductVariant

class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='carts', null=True, blank=True)
    session_key = models.CharField('Сессия', max_length=40, blank=True)
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