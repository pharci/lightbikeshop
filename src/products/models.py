import re

from django.db import models
from django.urls import reverse
from django.utils.text import slugify
import uuid
from django.utils.functional import cached_property
from unidecode import unidecode
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q, CheckConstraint, UniqueConstraint
from functools import cached_property
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill

class Category(models.Model):
    title = models.CharField('Название (основное)', max_length=50, db_index=True, unique=True)
    title_plural = models.CharField('Название (мн.ч.)', max_length=50, null=True, blank=True)
    title_singular = models.CharField('Название (ед.ч.)', max_length=50, null=True, blank=True)
    slug = models.SlugField('URL-ключ', max_length=50, db_index=True, unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="Родительская категория"
    )
    image = models.ImageField(upload_to="categories/", verbose_name="Изображение", null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title_plural or self.title

    class Meta:
        ordering = ("title",)
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
    
    def get_absolute_url(self):
        parts = []
        node = self
        while node:
            parts.append(node.slug)
            node = node.parent
        parts = reversed(parts)  # от корня к листу
        return reverse("products:category", kwargs={"category_path": "/".join(parts)})
    
    @cached_property
    def variant_attrs(self):
        return list(self.category_attributes
                    .select_related('attribute')
                    .filter(is_variant=True)
                    .order_by('sort_order', 'id'))

class Brand(models.Model):
    slug = models.SlugField('Название в ссылке', max_length=200, db_index=True, unique=True)
    title = models.CharField(max_length=100)
    image = models.ImageField(upload_to='brends/')
    description = models.TextField('Описание', blank=True, default='')
    def __str__(self):
        return self.title
    def get_absolute_url(self):
        return reverse('products:brand', args=[self.slug])
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Бренд'
        verbose_name_plural = 'Бренды'


class Attribute(models.Model):
    """
    Универсальный атрибут (Цвет, Размер, Объём…)
    Тип значения: text / number / bool (можно расширить)
    """
    TEXT = 'text'
    NUMBER = 'number'
    BOOL = 'bool'
    TYPE_CHOICES = [(TEXT, 'Текст'), (NUMBER, 'Число'), (BOOL, 'Да/Нет')]

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    value_type = models.CharField(max_length=12, choices=TYPE_CHOICES, default=TEXT)
    unit = models.CharField(max_length=32, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug: self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self): return self.name

    class Meta:
        verbose_name = 'Атрибут'
        verbose_name_plural = 'Атрибуты'


class CategoryAttribute(models.Model):
    """
    - is_filterable: попадает в фасетные фильтры
    - is_variant: по нему строятся вариации (цвет, размер…)
    """
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='category_attributes')
    attribute = models.ForeignKey(Attribute, on_delete=models.PROTECT, related_name='category_usages')

    is_filterable = models.BooleanField(default=True)
    is_variant    = models.BooleanField(default=False)
    sort_order    = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Атрибут категории'
        verbose_name_plural = 'Атрибуты категорий'
        unique_together = ('category', 'attribute')
        ordering = ['sort_order', 'id']

    def __str__(self):
        flags = []
        if self.is_filterable: flags.append('filter')
        if self.is_variant: flags.append('variant')
        return f'{self.category} :: {self.attribute} [{" ".join(flags)}]'

class Product(models.Model):
    id  = models.UUIDField(primary_key=True, default=uuid.uuid4)
    base_name = models.CharField('Название', max_length=200, null=True, blank=True)
    category = models.ForeignKey('Category', null=True, on_delete=models.PROTECT)
    brand = models.ForeignKey('Brand', null=True, blank=True, on_delete=models.PROTECT)
    description = models.TextField('Описание', null=True, blank=True)
    weight   = models.PositiveIntegerField('Вес для доставки, г', null=True, blank=True)
    created = models.DateTimeField('Дата создания', auto_now_add=True)
    updated = models.DateTimeField('Дата последнего обновления', auto_now=True)

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        indexes = [
            models.Index(fields=['category', 'brand', 'base_name']),
        ]

    def __str__(self):
        return f'{self.brand.title if self.brand else ""} {self.base_name}'.strip()

    @cached_property
    def variant_attributes(self):
        return self.category.variant_attrs if self.category_id else []

    @property
    def imageURL(self):
        # на случай если у товара нет ни одной фотки у варианта
        first_variant = self.variants.first()
        first_img = first_variant.images.first() if first_variant else None
        return first_img.image.url if first_img and first_img.image else ''



class Variant(models.Model):
    class FulfillmentType(models.TextChoices):
        STOCK = "stock", "В наличии"
        PREORDER = "preorder", "Под заказ"

    class SalesUnit(models.TextChoices):
        PIECE = "piece", "Штука"
        PAIR = "pair", "Пара"

    id  = models.UUIDField(primary_key=True, default=uuid.uuid4)
    product   = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    seller_article = models.CharField('Артикул продавца', max_length=64, null=True, blank=True)
    ozon_article = models.CharField('Артикул OZON', max_length=64, null=True, blank=True)
    wb_article = models.CharField('Артикул WB', max_length=64, null=True, blank=True)
    
    price     = models.DecimalField('Цена', max_digits=12, decimal_places=2)
    old_price = models.DecimalField('Старая цена', max_digits=12, decimal_places=2, null=True, blank=True)
    slug = models.SlugField('Ссылка', max_length=200, unique=True, editable=False, db_index=True)

    inventory = models.PositiveIntegerField('В наличии:', default=0)
    fulfillment_type = models.CharField("Тип продажи", max_length=16, choices=FulfillmentType.choices, default=FulfillmentType.STOCK, db_index=True)
    preorder_days_min = models.PositiveSmallIntegerField("Срок заказа от, дней", default=30)
    preorder_days_max = models.PositiveSmallIntegerField("Срок заказа до, дней", default=45)
    sales_unit = models.CharField("Единица продажи", max_length=8, choices=SalesUnit.choices, default=SalesUnit.PIECE)
    preorder_variant = models.OneToOneField(
        "self",
        verbose_name="Вариант для заказа",
        related_name="stock_offer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        limit_choices_to={"fulfillment_type": FulfillmentType.PREORDER},
        help_text="Более дешёвая позиция, которую можно заказать с ожиданием.",
    )
    new = models.BooleanField('Бейджик NEW', default=True)
    rec = models.BooleanField('Показывать на главной', default=False)
    is_active = models.BooleanField('Активный', default=True, db_index=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        max_len = self._meta.get_field('slug').max_length
        src  = (self.display_name() or self.id).strip()
        base = slugify(unidecode(src))
        base = base[:max_len]
        slug = base
        i = 2
        while self.__class__.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            suf = f'-{i}'
            slug = f'{base[:max_len-len(suf)]}{suf}'
            i += 1
        self.slug = slug
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.preorder_variant_id:
            if self.preorder_variant_id == self.pk:
                raise ValidationError({"preorder_variant": "Нельзя связать товар с самим собой."})
            if self.fulfillment_type != self.FulfillmentType.STOCK:
                raise ValidationError({"preorder_variant": "Под заказ можно привязать только к товару из наличия."})
            if self.preorder_variant.fulfillment_type != self.FulfillmentType.PREORDER:
                raise ValidationError({"preorder_variant": "Выберите товар с типом «Под заказ»."})

    @property
    def discount_percent(self):
        if self.old_price and self.old_price > 0 and self.price < self.old_price:
            return int(round(100 - (self.price / self.old_price * 100)))
        return 0

    @property
    def is_preorder(self):
        return self.fulfillment_type == self.FulfillmentType.PREORDER

    class Meta:
        verbose_name = 'Вариант'
        verbose_name_plural = 'Варианты'
        indexes = [
            models.Index(fields=['id']),
        ]

    def __str__(self):
        return f'{self.display_name()}'
    
    def variant_label(self):
        """
        Собирает подпись из ВАРИАНТНЫХ атрибутов (в порядке sort_order категории).
        Примеры: '2.3', 'Kevlar 2.4', 'Черный / L'
        """
        # значения атрибутов этого варианта
        vals = {v.attribute_id: v for v in self.attribute_values.select_related('attribute')}
        parts = []
        for ca in self.product.variant_attributes:
            val = vals.get(ca.attribute_id)
            if not val:
                continue
            a = ca.attribute
            if a.value_type == 'text':
                parts.append(val.value_text)
            elif a.value_type == 'number':
                s = str(val.value_number).rstrip('0').rstrip('.')
                parts.append(s)
            # Булевы характеристики полезны в таблице, но «Да/Нет» в названии
            # карточки выглядит как мусор и не помогает выбрать вариант.

        return ' '.join([p for p in parts if p])

    def display_name(self):
        p = self.product
        category = (getattr(p.category, 'title_singular', None)) if p.category else ''
        if p.category and p.category.title == "Втулки" and any(x in (p.base_name or "").lower() for x in ("хабсет", "набор втулок", "комплект втулок")):
            category = "Хабсет"
        brand    = getattr(p.brand, 'title', '').strip() if p.brand_id else ''
        base     = (p.base_name or '').strip()
        if brand:
            # Бренд выводится отдельно, поэтому убираем его повторы из начала модели.
            base = re.sub(rf"^(?:{re.escape(brand)}(?:[\s\-:]+|$))+", "", base, flags=re.I).strip()
        tail     = self.variant_label().strip()

        head = ' '.join(s for s in (category, brand, base) if s)
        if tail:
            return f'{head} {tail}'.strip()
        return head or self.id

    @property
    def sales_unit_label(self):
        return "пара" if self.sales_unit == self.SalesUnit.PAIR else "шт."

    @property
    def preorder_saving(self):
        if not self.preorder_variant_id:
            return 0
        return max(self.price - self.preorder_variant.price, 0)

    def main_image_url(self):
        img = self.images.first()
        return img.thumb.url if img and img.image else self.product.imageURL
    
    def get_absolute_url(self):
        category = self.product.category
        parts = []
        node = category
        while node:
            parts.append(node.slug)
            node = node.parent
        parts = reversed(parts)
        return reverse(
            "products:detail",
            kwargs={
                "category_path": "/".join(parts),
                "slug": self.slug,
            },
        )

    @cached_property
    def merged_attribute_values(self):
        prod = {av.attribute_id: av for av in self.product.attribute_values.all()}
        var  = {av.attribute_id: av for av in self.attribute_values.all()}
        prod.update(var)  # вариант перекрывает товар
        return sorted(prod.values(), key=lambda av: (av.attribute.name or "", av.attribute_id))


class StockVariant(Variant):
    class Meta:
        proxy = True
        verbose_name = "Товар в наличии"
        verbose_name_plural = "Товары в наличии"


class PreorderVariant(Variant):
    class Meta:
        proxy = True
        verbose_name = "Товар по под заказу"
        verbose_name_plural = "Товары по под заказу"


class Image(models.Model):
    """
    Галерея изображений товара.
    """
    variant = models.ForeignKey(Variant, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField('Изображение', upload_to='gallery/')
    thumb = ImageSpecField(
        source="image",
        processors=[ResizeToFill(300, 300)],
        format="WEBP",
        options={"quality": 65}
    )

    # основное изображение на странице товара
    medium = ImageSpecField(
        source="image",
        processors=[ResizeToFill(900, 900)],
        format="WEBP",
        options={"quality": 75}
    )

    # для lightbox (уменьшенный оригинал)
    large = ImageSpecField(
        source="image",
        processors=[ResizeToFill(1600, 1600)],
        format="WEBP",
        options={"quality": 85}
    )
    alt = models.CharField('Alt-текст', max_length=200, blank=True)
    sort = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        ordering = ['sort', 'id']
        verbose_name = 'Галерея'
        verbose_name_plural = 'Галерея'
        indexes = [
            models.Index(fields=['variant', 'sort']),
        ]


class AttributeValue(models.Model):
    """
    Значение атрибута для конкретной вариации (SKU).
    """
    product   = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='attribute_values', null=True, blank=True)
    variant   = models.ForeignKey(Variant, on_delete=models.CASCADE, related_name='attribute_values', null=True, blank=True)
    attribute = models.ForeignKey(Attribute, on_delete=models.PROTECT)

    value_text   = models.CharField(max_length=255, blank=True)
    value_number = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    value_bool   = models.BooleanField(null=True, blank=True)

    class Meta:
        verbose_name = 'Значение атрибута'
        verbose_name_plural = 'Значения атрибутов'
        constraints = [
            CheckConstraint(
                check=(
                    (Q(product__isnull=False) & Q(variant__isnull=True)) |
                    (Q(product__isnull=True) & Q(variant__isnull=False))
                ),
                name="attr_value_exactly_one_owner",
            ),
            UniqueConstraint(
                fields=["variant", "attribute"],
                condition=Q(variant__isnull=False),
                name="uniq_variant_attribute_when_variant",
            ),
            UniqueConstraint(
                fields=["product", "attribute"],
                condition=Q(product__isnull=False),
                name="uniq_product_attribute_when_product",
            ),
        ]

    def clean(self):
        if bool(self.product) == bool(self.variant):
            raise ValidationError("Укажите либо product, либо variant.")
        vt = [self.value_text, self.value_number, self.value_bool]
        if sum(v is not None and v != "" for v in vt) != 1:
            raise ValidationError("Должно быть заполнено ровно одно значение.")
        super().clean()

    def __str__(self):
        owner = self.variant or self.product
        return f"{owner} :: {self.attribute.name} = {self.display_value}"

    @property
    def display_value(self):
        if self.attribute.value_type == Attribute.TEXT:
            return self.value_text
        if self.attribute.value_type == Attribute.NUMBER:
            return self.value_number
        return 'Да' if self.value_bool else 'Нет'
    



class RelatedVariant(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        AUTO   = "auto",   "Auto"

    from_variant = models.ForeignKey(Variant, related_name="related_links",
                                     on_delete=models.CASCADE, db_index=True)
    to_variant   = models.ForeignKey(Variant, related_name="+",
                                     on_delete=models.CASCADE)
    source    = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)
    weight    = models.FloatField(default=1.0)
    position  = models.PositiveIntegerField(default=0)
    pinned    = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Связанные товары'
        constraints = [
            models.UniqueConstraint(fields=["from_variant","to_variant"], name="uniq_related_variant"),
            models.CheckConstraint(check=~models.Q(from_variant=models.F("to_variant")),
                                   name="no_self_link_variant"),
        ]
        indexes = [
            models.Index(fields=["from_variant","-pinned","-weight","position","id"]),
            models.Index(fields=["source","from_variant"]),
        ]

class CopurchaseVariantStat(models.Model):
    variant_min = models.ForeignKey(Variant, related_name="+", on_delete=models.CASCADE, db_index=True)
    variant_max = models.ForeignKey(Variant, related_name="+", on_delete=models.CASCADE, db_index=True)
    count = models.PositiveIntegerField(default=0)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Статистика вариантов по заказам'
        constraints = [
            models.UniqueConstraint(fields=["variant_min","variant_max"], name="uniq_copurchase_variant"),
            models.CheckConstraint(check=models.Q(variant_min__lt=models.F("variant_max")),
                                   name="ordered_pair_variant"),
        ]
        indexes = [models.Index(fields=["variant_min"]), models.Index(fields=["variant_max"])]


class TaobaoImportItem(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает проверки"
        IMPORTED = "imported", "Импортирован"
        REJECTED = "rejected", "Отклонён"

    source_key = models.CharField("Ключ Taobao", max_length=255, unique=True)
    store = models.CharField("Магазин", max_length=100)
    external_id = models.CharField("ID / SKU Taobao", max_length=200)
    title_original = models.TextField("Исходное название")
    title_ru = models.TextField("Название на русском", blank=True)
    description_ru = models.TextField("Описание", blank=True)
    category_name = models.CharField("Категория", max_length=100, blank=True)
    brand_name = models.CharField("Бренд", max_length=100, blank=True)
    variant_name = models.TextField("Вариант", blank=True)
    price_cny = models.DecimalField("Цена CNY", max_digits=12, decimal_places=2, null=True, blank=True)
    price_rub = models.DecimalField("Цена ₽", max_digits=12, decimal_places=2, null=True, blank=True)
    available = models.BooleanField("В наличии", default=True)
    image_url = models.URLField("Фото", max_length=1000, blank=True)
    product_url = models.URLField("Карточка Taobao", max_length=1000, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL, related_name="taobao_imports")
    variant = models.ForeignKey(Variant, null=True, blank=True, on_delete=models.SET_NULL, related_name="taobao_imports")
    raw = models.JSONField(default=dict, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        verbose_name = "Черновик Taobao"
        verbose_name_plural = "Черновики Taobao"
        indexes = [models.Index(fields=["status", "store", "updated_at"])]

    def __str__(self):
        return self.title_ru or self.title_original
