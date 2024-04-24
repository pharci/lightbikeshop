from django.db import models
from accounts.models import User
from store.models import ProductVariant, Warehouse
import uuid
from django.db.models.signals import post_save
from django.dispatch import receiver

# Измененный метод для генерации уникального номера заказа
def generate_order_id():
    return str(uuid.uuid4())[:10]

# Модель для отслеживания истории изменений заказа
class OrderHistory(models.Model):
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='history')
    status = models.ForeignKey('OrderStatus', on_delete=models.CASCADE)
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = 'История заказа'
        verbose_name_plural = 'Истории заказов'

class OrderStatus(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField("Описание")

# Обновленная модель Order
class Order(models.Model):
    order_id = models.CharField('Номер заказа', max_length=10, primary_key=True, default=generate_order_id, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='orders', null=True, blank=True)
    status = models.ForeignKey(OrderStatus, on_delete=models.PROTECT, null=True, blank=True)
    username = models.CharField('ФИО', max_length=100, null=False)
    contact_phone = models.CharField('Телефон', max_length=20)
    order_notes = models.TextField('Комментарий к заказу', null=True, blank=True)
    tracking_code = models.CharField('Код для отслеживания', max_length=50, null=True, blank=True)
    updated = models.DateTimeField("Последнее изменение", auto_now=True)
    created = models.DateTimeField("Дата создания", auto_now_add=True)
    total_price = models.DecimalField("Итоговая сумма", max_digits=12, decimal_places=2, default=0.00)

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        old_status = None
        if not is_new:
            old_status = Order.objects.get(pk=self.pk).status
        super().save(*args, **kwargs)

        if not is_new and old_status != self.status:
            OrderHistory.objects.create(order=self, status=self.status, changed_by=self.user)

    def get_total_price(self):
        orderitems = self.items.all()
        total = sum([item.count * item.product_variant.price for item in orderitems])
        shipping_cost = self.shipping.first().price if self.shipping.exists() else 0
        return total + shipping_cost

    def get_total_count(self):
        orderitems = self.items.all()
        return sum([item.count for item in orderitems])

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

@receiver(post_save, sender=OrderItem)
def update_order_total_on_item_change(sender, instance, **kwargs):
    instance.order.get_total_price()

class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='address', null=True, blank=True)
    address_line = models.TextField(max_length=254)
    city = models.CharField(max_length=50)
    postal_code = models.CharField(max_length=50)

    class Meta:
        verbose_name = 'Адрес'
        verbose_name_plural = 'Адреса'

class ShippingMethod(models.Model):
    METHOD_CHOICES = (
        ('delivery', 'Доставка'),
        ('pickup', 'Самовывоз'),
    )
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='shipping')
    pickup = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, related_name='pickup', null=True, blank=True)
    delivery = models.ForeignKey(Address, on_delete=models.SET_NULL, related_name='delivery', null=True, blank=True)
    shipping_type = models.CharField("Тип доставки", choices=METHOD_CHOICES, max_length=20)
    price = models.DecimalField("Цена", max_digits=10, decimal_places=2, default=0)
    description = models.TextField("Описание", blank=True, null=True)

    def __str__(self):
        return f"{self.shipping_type}"

    class Meta:
        verbose_name = 'Способ получения'
        verbose_name_plural = 'Способ получения'

@receiver(post_save, sender=ShippingMethod)
def update_order_total_on_shipping_change(sender, instance, **kwargs):
    instance.order.get_total_price()

class PaymentStatus(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField("Описание")

class PaymentMethod(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField("Описание")

class OrderPayment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='payment')
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT)
    transaction_id = models.CharField('Номер транзакции', max_length=100)
    amount = models.DecimalField("Цена", max_digits=10, decimal_places=2, default=0)
    status = models.ForeignKey(PaymentStatus, on_delete=models.PROTECT)
    updated = models.DateTimeField("Последнее изменение", auto_now=True)
    created = models.DateTimeField("Дата создания", auto_now_add=True)