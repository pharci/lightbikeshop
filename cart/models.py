from django.db import models
from accounts.models import User
from products.models import Product


class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart', null=True, blank=True)
    session_key = models.CharField('Ключ сессии, вас это не касается пидоры', max_length=40, blank=True)
    # Другие поля вашей модели Cart

    def add_product(self, product):
        # Добавить товар в корзину
        cart_item, created = CartItem.objects.get_or_create(cart=self, product=product)
        if not created:
            cart_item.quantity += 1
            cart_item.save()

    def get_product_count(self, product):
        try:
            cart_item = CartItem.objects.get(cart=self, product=product)
            return cart_item.quantity
        except CartItem.DoesNotExist:
            return 0

    def get_product_total_price(self, product):
        try:
            cart_item = CartItem.objects.get(cart=self, product=product)
            return cart_item.quantity * product.price
            
        except CartItem.DoesNotExist:
            return 0

    def remove_product(self, product):
        # Удалить товар из корзины
        try:
            cart_item = CartItem.objects.get(cart=self, product=product)
            if cart_item.quantity > 1:
                cart_item.quantity -= 1
                cart_item.save()

            else:
                cart_item.delete()
        except CartItem.DoesNotExist:
            pass

    def clear(self):
        # Очистить корзину
        CartItem.objects.filter(cart=self).delete()

    def get_cart_total_price(self):
        items = self.items.all()
        price = sum([item.product.price * item.quantity for item in items])
        return price

    def get_cart_total_count(self):
        items = self.items.all()
        count = sum([item.quantity for item in items])
        return count 

    class Meta:
        verbose_name = 'Корзина'
        verbose_name_plural = 'Корзины'

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items', db_column='Корзина')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, db_column='Товар')
    quantity = models.PositiveIntegerField('Количество', default=1)

    class Meta:
        verbose_name = 'Товар корзины'
        verbose_name_plural = 'Товары корзин'