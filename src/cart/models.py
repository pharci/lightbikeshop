from __future__ import annotations

import base64, secrets

from decimal import Decimal
from django.urls import reverse

from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Sum
from django.utils import timezone
import uuid

from products.models import Variant

User = get_user_model()


# ───────────────────────────── CART ───────────────────────────── #

class Cart(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='cart', null=True, blank=True, verbose_name="Пользователь"
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    # NEW: промокод, храним только ссылку. Сумму считаем «на лету».
    promo_code = models.ForeignKey(
        "PromoCode", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="carts", verbose_name="Промокод"
    )

    class Meta:
        verbose_name = 'Корзина'
        verbose_name_plural = 'Корзины'

    # --- позиционные методы ---
    def add_variant(self, variant: Variant):
        item, created = self.items.get_or_create(variant=variant)
        if not created:
            item.quantity += 1
        item.save(update_fields=["quantity"])

    def remove_variant(self, variant: Variant):
        try:
            item = self.items.get(variant=variant)
        except CartItem.DoesNotExist:
            return
        if item.quantity > 1:
            item.quantity -= 1
            item.save(update_fields=["quantity"])
        else:
            item.delete()

    def get_variant_count(self, variant: Variant) -> int:
        try:
            return int(self.items.get(variant=variant).quantity)
        except CartItem.DoesNotExist:
            return 0

    def get_variant_total_price(self, variant: Variant) -> Decimal:
        return Decimal(self.get_variant_count(variant)) * Decimal(variant.price)

    # --- суммы ---
    def get_cart_subtotal_price(self) -> Decimal:
        """Сумма без скидок."""
        total = Decimal("0")
        for item in self.items.select_related("variant"):
            total += Decimal(item.variant.price) * int(item.quantity)
        return total  # без округления

    def _compute_discount(self, subtotal: Decimal) -> Decimal:
        """Посчитать скидку от промокода (если применим)."""
        pc = self.promo_code
        if not pc:
            return Decimal("0")
        ok, _ = pc.can_apply(user=getattr(self, "user", None), subtotal=subtotal)
        if not ok:
            return Decimal("0")
        return Decimal(str(pc.calculate_discount(subtotal)))
    
    def get_promo_obj(self):
        if not self.promo_code:
            return None
        return self.promo_code
    
    def get_discount(self) -> Decimal:
        """Итог скидки по промокоду."""
        subtotal = self.get_cart_subtotal_price()
        discount = self._compute_discount(subtotal)
        return max(Decimal("0"), discount)

    def get_cart_total_price(self) -> Decimal:
        """Итог к оплате с учётом скидки промо."""
        subtotal = self.get_cart_subtotal_price()
        discount = self._compute_discount(subtotal)
        total = subtotal - discount
        return max(Decimal("0"), total)
    
    def get_total_weight(self):
        return sum((item.variant.product.weight or 0) * item.quantity for item in self.items.select_related('variant'))

    def get_total_items(self) -> int:
        return sum(item.quantity for item in self.items.all())

    # --- данные для фронта ---
    def get_items(self):
        rows = (self.items
                .select_related(
                    'variant', 'variant__product', 'variant__product__brand', 'variant__product__category'
                )
                .prefetch_related('variant__images'))
        data = []
        for ci in rows:
            v = ci.variant
            name = v.display_name() if hasattr(v, "display_name") and callable(v.display_name) else str(v)
            first_img = v.images.first()
            img_url = first_img.image.url if first_img and first_img.image else ""
            unit_price = float(v.price)
            item_total = int(round(unit_price * ci.quantity))
            data.append({
                "variant": {
                    "id": v.id,
                    "name": name,
                    "imageURL": img_url,
                    "main_image_url": getattr(v, "main_image_url", lambda: img_url)(),
                    "inventory": v.inventory,
                    "slug": v.slug or "",
                    "price": unit_price,
                    "product_url": v.get_absolute_url(),
                },
                "quantity": ci.quantity,
                "product_total_price": item_total
            })
        return data

    # --- промо-API для БД-корзины ---
    def apply_promo(self, promo: "PromoCode", user=None) -> tuple[bool, str]:
        """Сохранить промокод в корзину, если он применим к текущей сумме."""
        subtotal = self.get_cart_subtotal_price()
        ok, reason = promo.can_apply(user=user, subtotal=subtotal)
        if not ok:
            return False, reason
        self.promo_code = promo
        self.save(update_fields=["promo_code"])
        return True, ""

    def remove_promo(self):
        if self.promo_code_id:
            self.promo_code = None
            self.save(update_fields=["promo_code"])

    def clear(self):
        self.items.all().delete()
        self.promo_code = None
        self.save(update_fields=["promo_code"])


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart, on_delete=models.CASCADE, related_name='items', verbose_name='Корзина'
    )
    variant = models.ForeignKey(
        Variant, on_delete=models.CASCADE, verbose_name='Вариант'
    )
    quantity = models.PositiveIntegerField('Количество', default=1)

    class Meta:
        verbose_name = 'Товар корзины'
        verbose_name_plural = 'Товары корзин'
        constraints = [
            models.UniqueConstraint(fields=('cart', 'variant'), name='uniq_cart_variant')
        ]

    def __str__(self):
        return f"{self.variant} × {self.quantity}"


# ─────────────── CART (SESSION) ─────────────── #

class SessionCart:
    """
    Сессионная корзина {variant_id: qty} + промокод в session['promo_code'].
    Публичные методы совместимы с Cart.
    """
    SESSION_KEY = 'cart'
    PROMO_KEY = 'promo_code'

    def __init__(self, request):
        self.session = request.session
        self.session_key = self.SESSION_KEY
        cart = self.session.get(self.session_key) or {}
        self.session[self.session_key] = cart
        self.cart = cart

    # --- внутреннее сохранение ---
    def _save(self):
        self.session[self.session_key] = self.cart
        self.session.modified = True

    # --- позиции ---
    def add_variant(self, variant: Variant):
        vid = str(variant.id)
        self.cart[vid] = int(self.cart.get(vid, 0)) + 1
        self._save()

    def remove_variant(self, variant: Variant):
        vid = str(variant.id)
        if vid not in self.cart:
            return
        self.cart[vid] = int(self.cart[vid]) - 1
        if self.cart[vid] <= 0:
            del self.cart[vid]
        self._save()

    def get_variant_count(self, variant: Variant) -> int:
        return int(self.cart.get(str(variant.id), 0))

    def get_variant_total_price(self, variant: Variant) -> Decimal:
        return Decimal(self.get_variant_count(variant)) * Decimal(variant.price)

    # --- суммы ---
    def get_promo_obj(self):
        code = (self.session.get(self.PROMO_KEY) or "").strip().upper()
        if not code:
            return None
        from .models import PromoCode  # локальный импорт, чтобы избежать циклов при миграциях
        return PromoCode.objects.filter(code__iexact=code, is_active=True).first()
    
    def get_cart_subtotal_price(self) -> Decimal:
        ids = list(self.cart.keys())
        if not ids:
            return Decimal("0")
        total = Decimal("0")
        for v in Variant.objects.filter(id__in=ids).only("id", "price"):
            total += Decimal(v.price) * int(self.cart.get(str(v.id), 0))
        return total  # без округления

    def _compute_discount(self, subtotal: Decimal) -> Decimal:
        pc = self.get_promo_obj()
        if not pc:
            return Decimal("0")
        user = getattr(self.session, "user", None)  # не всегда есть
        ok, _ = pc.can_apply(user=None, subtotal=subtotal)  # аноним тоже ок
        if not ok:
            return Decimal("0")
        return Decimal(str(pc.calculate_discount(subtotal)))  # без .quantize

    def get_discount(self) -> Decimal:
        """Итог скидки по промо."""
        subtotal = self.get_cart_subtotal_price()
        discount = self._compute_discount(subtotal)
        return max(Decimal("0"), discount)  # без округления

    def get_cart_total_price(self) -> Decimal:
        subtotal = self.get_cart_subtotal_price()
        discount = self._compute_discount(subtotal)
        total = subtotal - discount
        return max(Decimal("0"), total)
    
    def get_total_weight(self) -> int:
        ids = list(self.cart.keys())
        if not ids:
            return 0
        total = 0
        for v in Variant.objects.filter(id__in=ids).select_related("product").only("id", "product__weight"):
            qty = int(self.cart.get(str(v.id), 0))
            w = int(v.product.weight or 0)
            total += w * qty
        return total

    def get_total_items(self) -> int:
        return sum(int(q) for q in self.cart.values())

    # --- данные для фронта ---
    def get_items(self):
        ids = list(self.cart.keys())
        if not ids:
            return []
        variants = (Variant.objects
                    .filter(id__in=ids)
                    .select_related('product', 'product__brand', 'product__category')
                    .prefetch_related('images'))
        out = []
        for v in variants:
            qty = int(self.cart.get(str(v.id), 0))
            name = v.display_name() if hasattr(v, "display_name") and callable(v.display_name) else str(v)
            first_img = v.images.first()
            img_url = first_img.image.url if first_img and first_img.image else ""
            unit_price = float(v.price)
            item_total = int(round(unit_price * qty))
            out.append({
                "variant": {
                    "id": v.id,
                    "name": name,
                    "imageURL": img_url,
                    "main_image_url": getattr(v, "main_image_url", lambda: img_url)(),
                    "inventory": v.inventory,
                    "slug": v.slug or "",
                    "price": unit_price,
                    "product_url": v.get_absolute_url(),
                },
                "quantity": qty,
                "product_total_price": item_total
            })
        return out

    # --- промо-API для сессионной корзины ---
    def apply_promo(self, promo: "PromoCode", user=None) -> tuple[bool, str]:
        subtotal = self.get_cart_subtotal_price()
        ok, reason = promo.can_apply(user=user, subtotal=subtotal)
        if not ok:
            return False, reason
        self.session[self.PROMO_KEY] = promo.code
        self.session.modified = True
        return True, ""

    def remove_promo(self):
        if self.PROMO_KEY in self.session:
            self.session.pop(self.PROMO_KEY, None)
            self.session.modified = True

    def clear(self):
        self.cart = {}
        self._save()
        self.remove_promo()


# ───────────────────────────── ORDERS ───────────────────────────── #

def gen_order_code(length=10) -> str:
    """
    Случайный код для заказа (публичный UUID-лайт).
    База: Base32 без '='. A-Z2-7. Только верхний регистр.
    Длина 12–16 символов = надёжность уровня UUID.
    """
    raw = secrets.token_bytes(10)  # 80 бит случайности
    b32 = base64.b32encode(raw).decode("ascii").rstrip("=")  # A-Z2-7
    return b32[:length].upper()


def gen_access_key():
    return secrets.token_urlsafe(24)


class Order(models.Model):
    STATUS_CHOICES = (
        ('created', 'Новый'),
        ('confirmed', 'Подтвержден'),
        ('assembled', 'Собран'),
        ('pickup', 'Самовывоз'),
        ('shipped', 'Отправлен'),
        ('delivered', 'Доставлен'),
        ('returned', 'Возврат'),
        ('canceled', 'Отменен'),
        ('auth', 'Платеж авторизован'),
        ('paid', 'Оплачен'),
        ('declined', 'Отклонен'),
        ('partial_return', 'Частичный возврат'),
    )
    PAYMENT_CHOICES = (('online', 'Онлайн'),)  # только онлайн

    order_id = models.CharField(
        "Код заказа", max_length=20,
        unique=True, db_index=True,
        default=gen_order_code,
        editable=False,
    )

    ms_order_id = models.UUIDField(
        "ID Мой склад", unique=True, editable=False, null=True, blank=True
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Пользователь")
    
    access_key = models.CharField("Ключ доступа", max_length=48, unique=True,
                                  default=gen_access_key, editable=False)

    status = models.CharField('Статус', max_length=200, choices=STATUS_CHOICES, default='created', db_index=True)
    user_name = models.CharField('ФИО', max_length=200)
    contact_phone = models.CharField('Телефон', max_length=20)
    email = models.EmailField('Почта', null=True, blank=True)
    order_notes = models.TextField('Комментарий к заказу', null=True, blank=True)

    subtotal = models.DecimalField("Сумма без скидок",max_digits=10, decimal_places=2,default=0, validators=[MinValueValidator(0)])
    discount_total = models.DecimalField("Скидка всего", max_digits=10, decimal_places=2,default=0, validators=[MinValueValidator(0)])
    shipping_total = models.DecimalField("Доставка",max_digits=10, decimal_places=2,default=0, validators=[MinValueValidator(0)])
    total = models.DecimalField("Итого к оплате",max_digits=10, decimal_places=2,default=0, validators=[MinValueValidator(0)])

    payment_type   = models.CharField('Тип оплаты', max_length=20, choices=PAYMENT_CHOICES, default='online')
    payment_url  = models.URLField("Ссылка на оплату", blank=True)

    city = models.CharField('Город', max_length=120, db_index=True, blank=True, default="")
    pvz_address = models.CharField('Адрес ПВЗ', max_length=255, blank=True)
    pvz_code    = models.CharField('Код ПВЗ', max_length=64, blank=True)

    promo_code = models.ForeignKey(
        "PromoCode", null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Промокод", related_name="orders"
    )

    date_ordered = models.DateTimeField('Дата создания', auto_now_add=True)
    updated = models.DateTimeField('Дата обновления', auto_now=True)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ("-date_ordered",)

    def __str__(self):
        return f'Заказ {self.order_id}'

    def get_total_count(self) -> int:
        agg = self.items.aggregate(total=Sum('quantity'))
        return int(agg['total'] or 0)
    
    def get_absolute_url(self):
        return reverse("cart:order_detail", args=[self.order_id]) + f"?k={self.access_key}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name="Заказ")
    variant = models.ForeignKey(Variant, on_delete=models.PROTECT, related_name='order_items', verbose_name="Вариант")
    price = models.DecimalField('Цена за единицу (snapshot)', max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField('Количество', default=1)
    amount = models.DecimalField('Сумма позиции', max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = 'Товар заказа'
        verbose_name_plural = 'Товары заказов'

    def __str__(self):
        return f'{self.variant} × {self.quantity}'

    @property
    def line_total(self) -> Decimal:
        return Decimal(self.price) * self.quantity


class PickupPoint(models.Model):
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Код"
    )
    slug = models.SlugField(unique=True, verbose_name="Слаг")
    title = models.CharField(max_length=120, verbose_name="Название")
    city = models.CharField(max_length=100, db_index=True, verbose_name="Город")
    address = models.CharField(max_length=255, verbose_name="Адрес")
    metro = models.CharField(max_length=100, verbose_name="Ближайшее метро", null=True, blank=True)
    lat = models.FloatField(verbose_name="Широта", default=0)
    lon = models.FloatField(verbose_name="Долгота", default=0)
    schedule = models.CharField(max_length=180, blank=True, default="", verbose_name="График")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    is_main = models.BooleanField(default=False, verbose_name="Отображать на главной")
    sort = models.PositiveIntegerField(default=100, verbose_name="Сортировка")

    class Meta:
        ordering = ["city", "sort", "title"]
        verbose_name = "Пункт самовывоза"
        verbose_name_plural = "Пункты самовывоза"

    def __str__(self):
        return f"{self.code} — {self.city}"


# ───────────────────────────── PROMO ───────────────────────────── #

class PromoCode(models.Model):
    PERCENT = "percent"
    FIXED = "fixed"
    DISCOUNT_TYPES = (
        (PERCENT, "Процент"),
        (FIXED, "Фиксированная сумма"),
    )

    code = models.CharField("Код", max_length=50, unique=True, db_index=True)
    discount_type = models.CharField("Тип скидки", max_length=16, choices=DISCOUNT_TYPES, default=PERCENT)
    amount = models.DecimalField("Размер скидки", max_digits=10, decimal_places=2,
                                 validators=[MinValueValidator(0)])
    is_active = models.BooleanField("Активен", default=True)
    starts_at = models.DateTimeField("Начало действия", null=True, blank=True)
    ends_at = models.DateTimeField("Окончание действия", null=True, blank=True)
    usage_limit = models.PositiveIntegerField("Общий лимит применений", null=True, blank=True)
    used_count = models.PositiveIntegerField("Сколько раз применён", default=0)
    per_user_limit = models.PositiveIntegerField("Лимит на пользователя", null=True, blank=True)
    min_order_total = models.DecimalField("Мин. сумма заказа", max_digits=10, decimal_places=2,
                                          null=True, blank=True, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Промокод"
        verbose_name_plural = "Промокоды"
        ordering = ("-updated_at",)

    def __str__(self) -> str:
        return self.code.upper()

    # === Логика ===
    def is_within_date(self, now=None) -> bool:
        now = now or timezone.now()
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        return True

    def is_under_global_limit(self) -> bool:
        return self.usage_limit is None or self.used_count < self.usage_limit

    def calculate_discount(self, subtotal: float | int | Decimal) -> float:
        subtotal = float(subtotal or 0)
        if self.discount_type == self.PERCENT:
            pct = max(0.0, min(float(self.amount), 100.0))
            return round(subtotal * (pct / 100.0), 2)
        return round(max(0.0, min(float(self.amount), subtotal)), 2)

    def can_apply(self, *, user=None, subtotal: float | int | Decimal = 0, now=None) -> tuple[bool, str]:
        if not self.is_active:
            return False, "Промокод не активен"
        if not self.is_within_date(now):
            return False, "Промокод вне периода действия"
        if not self.is_under_global_limit():
            return False, "Лимит использования промокода исчерпан"
        if self.min_order_total and float(subtotal) < float(self.min_order_total):
            return False, "Недостаточная сумма заказа"

        if self.per_user_limit and user and getattr(user, "is_authenticated", False):
            used = Order.objects.filter(user=user, promo_code=self).count()
            if used >= self.per_user_limit:
                return False, "Лимит промокода на пользователя исчерпан"
        return True, ""