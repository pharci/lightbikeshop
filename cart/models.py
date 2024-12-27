from django.db import models
from accounts.models import User
from store.models import ProductVariant
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import datetime
from django.db import transaction
from django.db.models import F

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

    @classmethod
    def get_cart(cls, request):
        if request.user.is_authenticated:
            return cls.objects.filter(user=request.user).first()
        else:
            cart_id = request.session.get('cart_id')
            if cart_id:
                return cls.objects.filter(id=cart_id).first()
        return None
    
    @classmethod
    def create_cart(cls, request):
        if request.user.is_authenticated:
            cart, created = cls.objects.get_or_create(user=request.user)
        else:
            cart_id = request.session.get('cart_id')
            if cart_id:
                cart = cls.objects.filter(id=cart_id).first()
            if not cart_id or not cart:
                cart = cls.objects.create()
                request.session['cart_id'] = cart.id
        return cart

    def add(self, variant, quantity=1):
        with transaction.atomic():
            cart_item, created = CartItem.objects.select_for_update().get_or_create(
                cart=self,
                variant=variant,
                defaults={'quantity': quantity}
            )
            if not created:
                cart_item.quantity += int(quantity)
                cart_item.save()

        return cart_item
    
    def remove(self, variant, quantity=1):
        with transaction.atomic():
            try:
                cart_item = CartItem.objects.select_for_update().get(cart=self, variant=variant)
                cart_item.quantity -= int(quantity)
                if cart_item.quantity <= 0:
                    cart_item.delete()
                else:
                    cart_item.save()
                return cart_item
            
            except CartItem.DoesNotExist:
                return 0

    def get_cart_total_price(self):
        items = self.items.all()
        price = sum([item.variant.price * item.quantity for item in items])
        return price

    def get_cart_total_count(self):
        items = self.items.all()
        quantity = sum([item.quantity for item in items])
        return quantity 

    class Meta:
        verbose_name = 'Корзина'
        verbose_name_plural = 'Корзины'

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField('Количество', default=1)

    class Meta:
        verbose_name = 'Товар корзины'
        verbose_name_plural = 'Товары корзин'