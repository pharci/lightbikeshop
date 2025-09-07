from django.db import models
from django.urls import reverse
from django.utils.text import slugify
import uuid
from django.utils.functional import cached_property
from decimal import Decimal
from django.core.validators import MinValueValidator
from unidecode import unidecode
from django.utils import timezone

class Category(models.Model):
    name = models.CharField('Название', max_length=200, db_index=True)
    second_name = models.CharField('Для склейки', max_length=200, null=True, blank=True)
    slug = models.SlugField('Ссылка', max_length=200, db_index=True, unique=True)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children"
    )
    image = models.ImageField(upload_to='categories/')

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self): return self.name

    class Meta:
        ordering = ('name',)
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
    
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
    def __str__(self):
        return self.title
    def get_absolute_url(self):
        return reverse('products:product_list_by_brand', args=[self.slug])
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
    Привязка атрибутов к категории + флаги:
    - is_required: обязателен для SKU
    - is_filterable: попадает в фасетные фильтры
    - is_variant: по нему строятся вариации (цвет, размер…)
    """
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='category_attributes')
    attribute = models.ForeignKey(Attribute, on_delete=models.PROTECT, related_name='category_usages')

    is_required   = models.BooleanField(default=False)
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
        if self.is_required: flags.append('req')
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
    id  = models.UUIDField(primary_key=True, default=uuid.uuid4)
    product   = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    ozon_article = models.CharField('OZON Артикул', max_length=64, null=True, blank=True)
    ozon_sku = models.CharField('OZON SKU', max_length=64, null=True, blank=True)
    
    price     = models.DecimalField('Цена', max_digits=12, decimal_places=2)
    old_price = models.DecimalField('Старая цена', max_digits=12, decimal_places=2, null=True, blank=True)
    slug = models.SlugField('Ссылка', max_length=200, unique=True, editable=False, db_index=True)

    inventory = models.PositiveIntegerField('В наличии:', default=0)
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

    @property
    def discount_percent(self):
        if self.old_price and self.old_price > 0 and self.price < self.old_price:
            return int(round(100 - (self.price / self.old_price * 100)))
        return 0

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
            else:
                parts.append('Да' if val.value_bool else 'Нет')

        return ' '.join([p for p in parts if p])

    def display_name(self):
        p = self.product
        category = (getattr(p.category, 'second_name', None) or getattr(p.category, 'name', '')).strip() if p.category_id else ''
        brand    = getattr(p.brand, 'title', '').strip() if p.brand_id else ''
        base     = (p.base_name or '').strip()
        tail     = self.variant_label().strip()

        head = ' '.join(s for s in (category, brand, base) if s)
        if tail:
            return f'{head} {tail}'.strip()
        return head or self.id

    def main_image_url(self):
        img = self.images.first()
        return img.image.url if img and img.image else self.product.imageURL
    
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


class Image(models.Model):
    """
    Галерея изображений товара.
    """
    variant = models.ForeignKey(Variant, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField('Изображение', upload_to='gallery/')
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
    variant   = models.ForeignKey(Variant, on_delete=models.CASCADE, related_name='attribute_values')
    attribute = models.ForeignKey(Attribute, on_delete=models.PROTECT)

    value_text   = models.CharField(max_length=255, blank=True)
    value_number = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    value_bool   = models.BooleanField(null=True, blank=True)

    class Meta:
        verbose_name = 'Значение атрибута'
        verbose_name_plural = 'Значения атрибутов'
        unique_together = ('variant', 'attribute')

    def clean(self):
        # Разрешаем ТОЛЬКО одно поле значения по типу атрибута
        vt = [self.value_text, self.value_number, self.value_bool]
        if sum(v is not None and v != '' for v in vt) != 1:
            raise ValidationError('Должно быть заполнено ровно одно значение атрибута.')
        super().clean()

    def __str__(self):
        return f'{self.variant} :: {self.attribute.name} = {self.display_value}'

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
