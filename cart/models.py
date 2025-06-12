from django.db import models
from accounts.models import User
from products.models import Product


class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def add_product(self, product):
        item, created = self.items.get_or_create(product=product)
        if not created:
            item.quantity += 1
        item.save()

    def remove_product(self, product):
        try:
            item = self.items.get(product=product)
            if item.quantity > 1:
                item.quantity -= 1
                item.save()
            else:
                item.delete()
        except CartItem.DoesNotExist:
            pass

    def get_product_count(self, product):
        try:
            item = self.items.get(product=product)
            return item.quantity
        except CartItem.DoesNotExist:
            return 0

    def get_product_total_price(self, product):
        count = self.get_product_count(product)
        return count * product.price

    def get_cart_total_price(self):
        total = 0
        for item in self.items.all():
            total += item.quantity * item.product.price
        return total

    def get_total_items(self):
        return sum(item.quantity for item in self.items.all())
    
    def get_items(self):
        return [{'product': item.product, 'quantity': item.quantity} for item in self.items.all()]

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


class SessionCart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get('cart')
        if not cart:
            cart = self.session['cart'] = {}
        self.cart = cart

    def add_product(self, product):
        pid = str(product.id)
        self.cart[pid] = self.cart.get(pid, 0) + 1
        self.session.modified = True

    def remove_product(self, product):
        pid = str(product.id)
        if pid in self.cart:
            self.cart[pid] -= 1
            if self.cart[pid] <= 0:
                del self.cart[pid]
            self.session.modified = True

    def get_product_count(self, product):
        return self.cart.get(str(product.id), 0)

    def get_product_total_price(self, product):
        count = self.get_product_count(product)
        return count * product.price

    def get_cart_total_price(self):
        from products.models import Product
        total = 0
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids)
        for product in products:
            quantity = self.cart.get(str(product.id), 0)
            total += product.price * quantity
        return total

    def get_total_items(self):
        return sum(self.cart.values())
    
    def get_items(self):
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids)
        return [{'product': p, 'quantity': self.cart.get(str(p.id), 0)} for p in products]