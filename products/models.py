from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils.functional import cached_property

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
    external_id = models.UUIDField(unique=True, null=True, blank=True, db_index=True)
    slug = models.SlugField('Ссылка', max_length=200, db_index=True)
    base_name = models.CharField('Название', max_length=200, null=True, blank=True)
    category = models.ForeignKey('Category', null=True, on_delete=models.PROTECT)
    brand = models.ForeignKey('Brand', null=True, blank=True, on_delete=models.CASCADE)

    description = models.TextField('Описание', null=True, blank=True)

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
    
    def save(self, *args, **kwargs):
        if not self.slug:
            # можно включить бренд в слаг
            prefix = f'{self.brand.slug}-' if self.brand else ''
            self.slug = slugify(f'{prefix}{self.base_name}')[:200]
        super().save(*args, **kwargs)

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
    """
    SKU: конкретная вариация товара (цвет/размер/…)
    """
    product   = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    external_id = models.UUIDField(unique=True, null=True, blank=True, db_index=True)
    sku = models.CharField(max_length=255, blank=True, null=True)
    price     = models.DecimalField(max_digits=12, decimal_places=2)

    # внешние артикула/ссылки (WB, Ozon)
    wb_article   = models.CharField(max_length=64, blank=True)
    ozon_article = models.CharField(max_length=64, blank=True)

    inventory = models.PositiveIntegerField(default=0)  # общий остаток для вариации
    new = models.BooleanField(default=True)
    rec = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Вариант'
        verbose_name_plural = 'Варианты'
        indexes = [
            models.Index(fields=['product']),
        ]

    def __str__(self):
        return f'{self.product} [{self.sku}]'
    
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
        """Полное имя варианта для списка и карточек."""
        category = ""
        brand = ""
        base_name = ""
        if self.product.category.second_name: category = self.product.category.second_name
        if self.product.brand: brand = self.product.brand.title
        if self.product.base_name: base_name = self.product.base_name
        tail = self.variant_label()
        return f"{category} {brand} {base_name} {tail}".strip()

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
                "slug": self.product.slug,
                "variant_id": self.id,
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