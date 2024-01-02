from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid

class Category(models.Model):
    name = models.CharField("Название", max_length=100, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    is_part = models.BooleanField("Другая категория", default=False)
    image = models.ImageField("Фото", upload_to='categories/')

    def get_absolute_url(self):
        return reverse('products:product_list', args=[self.slug])

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

class Brand(models.Model):
    name = models.CharField("Название", max_length=100, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    image = models.ImageField("Фото", upload_to='brands/')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Бренд'
        verbose_name_plural = 'Бренды'

class Product(models.Model):
    category = models.ForeignKey(Category, verbose_name="Категория", on_delete=models.PROTECT)
    brand = models.ForeignKey(Brand, verbose_name="Бренд", on_delete=models.CASCADE)
    name = models.CharField("Название", max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField("Описание")
    created = models.DateTimeField("Дата создания", auto_now_add=True)
    updated = models.DateTimeField("Последнее изменение", auto_now=True)


    def save(self, *args, **kwargs):
        self.slug = slugify(self.name) if not self.slug else self.slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'

class ProductVariant(models.Model):
    product = models.ForeignKey(Product, verbose_name="Product", related_name='variants', on_delete=models.CASCADE)
    sku = models.CharField("Артикул", max_length=100, unique=True, blank=True)
    price = models.DecimalField("Цена", max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    count = models.PositiveSmallIntegerField("Количество", default=0, validators=[MinValueValidator(0)])
    recommendation = models.BooleanField(default=False)
    new = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.sku:
            self.sku = str(uuid.uuid4()).split('-')[0].upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} - {self.sku}"

    def get_absolute_url(self):
        return reverse('products:product_detail', args=[self.product.category.slug, self.product.brand.slug, self.sku, self.product.slug])

    def get_first_image_url(self):
        first_image = ProductImage.objects.filter(variant=self).first()
        if first_image:
            return first_image.image.url
        return ''

    def get_full_name(self):
        main_attributes = self.attributes.filter(is_main=True)
        attribute_values = [f'{attr.value}{attr.unit}' for attr in main_attributes]
        return f"{self.product.name} {' '.join(attribute_values)}"

    class Meta:
        verbose_name = 'Вариация товара'
        verbose_name_plural = 'Вариации товаров'

class Attribute(models.Model):
    name = models.CharField("Атрибут", max_length=100)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Атрибут'
        verbose_name_plural = 'Атрибуты'

class AttributeValue(models.Model):
    variant = models.ForeignKey(ProductVariant, verbose_name="Вариация продукта", related_name='attributes', on_delete=models.CASCADE)
    attribute = models.ForeignKey(Attribute, verbose_name="Атрибут", on_delete=models.CASCADE)
    value = models.CharField("Значение", max_length=100)
    unit = models.CharField("Единица измерения", max_length=100, blank=True)
    is_main = models.BooleanField("Отображать в названии", default=False)

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"

    class Meta:
        verbose_name = 'Значение атрибута'
        verbose_name_plural = 'Значение атрибутов'

class ProductImage(models.Model):
    variant = models.ForeignKey(ProductVariant, verbose_name="Вариация продукта", related_name='images', on_delete=models.CASCADE)
    image = models.ImageField("Фото", upload_to='products/')

    def __str__(self):
        return f"Фото для {self.variant}"

    def get_image_url(self):
        return self.image.url

    class Meta:
        verbose_name = 'Фото товара'
        verbose_name_plural = 'Фото товаров'

        