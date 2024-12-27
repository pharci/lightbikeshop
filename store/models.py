from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid
from accounts.models import User
from django.db.models import Sum

class Category(models.Model):
    name = models.CharField("Название", max_length=100, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    image = models.ImageField("Фото", upload_to='categories/')
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True, verbose_name="Родительская категория")

    def get_absolute_url(self):
        return reverse('store:catalog', args=[self.slug])

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

class Brand(models.Model):
    name = models.CharField("Название", max_length=100, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField("Описание", blank=True, null=True)
    image = models.ImageField("Фото", upload_to='brands/')
    updated = models.DateTimeField("Последнее изменение", auto_now=True)
    created = models.DateTimeField("Дата создания", auto_now_add=True)

    def get_absolute_url(self):
        return reverse('store:brands', args=[self.slug])

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Бренд'
        verbose_name_plural = 'Бренды'

class Product(models.Model):
    category = models.ForeignKey(Category, verbose_name="Категория", related_name='products', on_delete=models.PROTECT)
    brand = models.ForeignKey(Brand, verbose_name="Бренд", related_name='products', on_delete=models.CASCADE)
    name = models.CharField("Название", max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField("Описание")
    meta_description = models.TextField("Краткое описание")
    meta_keywords = models.TextField("Ключевые слова")
    updated = models.DateTimeField("Последнее изменение", auto_now=True)
    created = models.DateTimeField("Дата создания", auto_now_add=True)


    def save(self, *args, **kwargs):
        self.slug = slugify(self.name) if not self.slug else self.slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'

class ProductVariant(models.Model):
    product = models.ForeignKey(Product, verbose_name="Товар", related_name='variants', on_delete=models.CASCADE)
    sku = models.CharField("Артикул", max_length=100, unique=True, blank=True)
    price = models.DecimalField("Цена", max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('1'))])
    old_price = models.DecimalField("Старая цена", max_digits=10, decimal_places=2, null=True, blank=True)
    is_discounted = models.BooleanField("Скидка", default=False)
    recommendation = models.BooleanField("Рекомендация", default=False)
    new = models.BooleanField("Новинка", default=False)

    def save(self, *args, **kwargs):
        if not self.sku:
            self.sku = str(uuid.uuid4()).split('-')[0].upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} - {self.sku}"

    def get_absolute_url(self):
        return reverse('store:product_detail', args=[self.product.category.slug, self.product.brand.slug, self.product.slug, self.sku])

    def get_first_image_url(self):
        first_image = ProductImage.objects.filter(variant=self).first()
        if first_image:
            return first_image.image.url
        return ''

    def get_full_name(self):
        main_attributes = self.attribute_variants.filter(is_main=True)
        attribute_values = [f'{attr.value.value}' for attr in main_attributes]
        return f"{self.product.category.name} {self.product.brand.name} {self.product.name} {' '.join(attribute_values)}"
    
    def total_inventory(self):
        return self.inventory.aggregate(total=Sum('stock_level'))['total'] or 0
    
    def get_variant_quantity_in_cart(request, variant_id):
        from cart.models import Cart, CartItem
        if request.user.is_authenticated:
            cart = Cart.objects.filter(user=request.user)
        else:
            session_key = request.session.session_key
            if not session_key:
                return 0
            cart = Cart.objects.filter(session_key=session_key)

        if cart.exists():
            try:
                cart_item = cart.items.get(variant__id=variant_id)
                return cart_item.quantity
            except CartItem.DoesNotExist:
                return 0
        return 0

    class Meta:
        verbose_name = 'Вариация товара'
        verbose_name_plural = 'Вариации товаров'


class Attribute(models.Model):
    name = models.CharField("Атрибут", max_length=100)
    slug = models.SlugField(max_length=200, unique=True)
    unit = models.CharField("Единица измерения", max_length=10, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Атрибут'
        verbose_name_plural = 'Атрибуты'

class AttributeValue(models.Model):
    attribute = models.ForeignKey(Attribute, verbose_name="Атрибут", related_name='values', on_delete=models.CASCADE)
    value = models.CharField("Значение (Отображаемое)", max_length=100)
    value_en = models.CharField("Значение EN (Серверное)", max_length=100, blank=True)

    def __str__(self):
        return self.value

    class Meta:
        verbose_name = 'Значение атрибута'
        verbose_name_plural = 'Значения атрибутов'

class AttributeVariant(models.Model):
    variant = models.ForeignKey(ProductVariant, verbose_name="Вариация продукта", related_name='attribute_variants', on_delete=models.CASCADE)
    attribute = models.ForeignKey(Attribute, verbose_name="Атрибут", related_name='attribute_variants', on_delete=models.CASCADE)
    value = models.ForeignKey(AttributeValue, verbose_name="Значение", related_name='attribute_variants', on_delete=models.CASCADE)
    is_main = models.BooleanField("Отображать в названии", default=False)
    is_filter = models.BooleanField("Отображать в фильтре", default=True)

    def __str__(self):
        return f"{self.attribute.name}: {self.value.value}"
    
    class Meta:
        verbose_name = 'Атрибут варианта товара'
        verbose_name_plural = 'Атрибуты варианта товара'
        unique_together = ('variant', 'attribute')


class Warehouse(models.Model):
    name = models.CharField("Название", max_length=100)
    address_line = models.TextField(max_length=254)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        verbose_name = 'Склады'
        verbose_name_plural = 'Склад'


class Inventory(models.Model):
    product_variant = models.ForeignKey(ProductVariant, related_name='inventory', on_delete=models.PROTECT)
    warehouse = models.ForeignKey(Warehouse, related_name='inventory', on_delete=models.PROTECT, null=True)
    stock_level = models.IntegerField("Количество", default=0, validators=[MinValueValidator(0)])
    low_stock_threshold = models.PositiveIntegerField("Порог низкого запаса", default=5)
    low_stock_alert = models.BooleanField("На исходе", default=False)

    def save(self, *args, **kwargs):
        if self.stock_level <= self.low_stock_threshold:
            self.low_stock_alert = True
        else:
            self.low_stock_alert = False

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Инвентарь для {self.product_variant}"

    class Meta:
        verbose_name = 'Инвентарь'
        verbose_name_plural = 'Инвентарь'


class ProductImage(models.Model):
    variant = models.ForeignKey(ProductVariant, verbose_name="Вариация продукта", related_name='images', on_delete=models.CASCADE)
    image = models.ImageField("Фото", upload_to='products/')
    is_main = models.BooleanField("Главное фото", default=False)

    def __str__(self):
        return f"Фото для {self.variant}"

    def get_image_url(self):
        return self.image.url

    class Meta:
        verbose_name = 'Фото товара'
        verbose_name_plural = 'Фото товаров'


class Wishlist(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wishlist')

    class Meta:
        verbose_name = 'Список избранного'
        verbose_name_plural = 'Списки избранного'

class WishlistItem(models.Model):
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name='items')
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    added_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Избранный товар'
        verbose_name_plural = 'Избранные товары'


class ProductReview(models.Model):
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='reviews', verbose_name="Продукт")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews', verbose_name="Пользователь")
    rating = models.PositiveSmallIntegerField("Рейтинг", default=1)
    comment = models.TextField("Комментарий", blank=True)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)

    def __str__(self):
        return f"Отзыв от {self.user.username} на {self.product_variant.product.name} {self.product_variant}"

    class Meta:
        verbose_name = 'Отзыв о продукте'
        verbose_name_plural = 'Отзывы о продуктах'
        unique_together = ['product_variant', 'user']