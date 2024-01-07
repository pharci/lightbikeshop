import nested_admin
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid
from django import forms
from django.db import models

from .models import *

class InventoryAdmin(admin.ModelAdmin):
    list_display = ('name_preview', 'stock_level', 'low_stock_threshold', 'low_stock_alert')
    list_filter = ('low_stock_alert',)
    search_fields = ('product_variant__name',)
    list_editable = ('stock_level', 'low_stock_threshold')
    readonly_fields = ('low_stock_alert',)

    def save_model(self, request, obj, form, change):
        if obj.stock_level <= obj.low_stock_threshold:
            obj.low_stock_alert = True
        else:
            obj.low_stock_alert = False
        super().save_model(request, obj, form, change)

    def name_preview(self, obj):
        return obj.product_variant.get_full_name()
    name_preview.short_description = 'Полное название'

admin.site.register(Inventory, InventoryAdmin)

class InventoryInline(nested_admin.NestedTabularInline):
    model = Inventory
    extra = 1
    verbose_name = "Инвентарь"
    verbose_name_plural = "Инвентарь"



@admin.register(ProductReview)
class ProductReview(admin.ModelAdmin):
    list_display = ['product_variant', 'user', 'rating']
    list_filter = ['user', 'product_variant']





class AttributeValueInline(nested_admin.NestedTabularInline):
    model = AttributeValue
    extra = 1
    formfield_overrides = {
        models.CharField: {'widget': forms.TextInput(attrs={'size': '20'})},
    }
    verbose_name = "Значение атрибута"
    verbose_name_plural = "Значения атрибутов"

class ProductImageInline(nested_admin.NestedTabularInline):
    model = ProductImage
    extra = 1
    readonly_fields = ['image_preview']
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 150px; height: auto;" />', obj.image.url)
        return "Изображение не найдено"
    image_preview.short_description = 'Предпросмотр изображения'

class ProductVariantInline(nested_admin.NestedStackedInline):
    model = ProductVariant
    extra = 0
    inlines = [AttributeValueInline, ProductImageInline, InventoryInline]
    readonly_fields = ['sku', 'name_preview']
    formfield_overrides = {
        models.DecimalField: {'widget': forms.NumberInput(attrs={'step': '0.01'})},
    }
    verbose_name = "Вариант продукта"
    verbose_name_plural = "Варианты продуктов"

    def name_preview(self, obj):
        return obj.get_full_name()
    name_preview.short_description = 'Полное название'


@admin.register(Product)
class ProductAdmin(nested_admin.NestedModelAdmin):
    list_display = ['name', 'category', 'brand']
    list_filter = ['category', 'brand']
    search_fields = ['name', 'description', 'category__name', 'brand__name']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductVariantInline]
    formfield_overrides = {
        models.CharField: {'widget': forms.TextInput(attrs={'size': '40'})},
        models.TextField: {'widget': forms.Textarea(attrs={'rows': 4, 'cols': 40})},
    }
    verbose_name = "Продукт"
    verbose_name_plural = "Продукты"

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'image_preview']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 100px; height: auto;" />', obj.image.url)
        return "Изображение не найдено"
    image_preview.short_description = 'Изображение'

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'image_preview']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 100px; height: auto;" />', obj.image.url)
        return "Изображение не найдено"
    image_preview.short_description = 'Изображение'

@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']

@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['product', 'sku', 'price', 'recommendation', 'new', 'display_attributes', 'image_preview']
    list_filter = ['product']
    search_fields = ['sku', 'product__name']
    inlines = [AttributeValueInline, ProductImageInline, InventoryInline]
    formfield_overrides = {
        models.DecimalField: {'widget': forms.NumberInput(attrs={'step': '0.01'})},
    }

    def save_model(self, request, obj, form, change):
        if not obj.sku:
            obj.sku = str(uuid.uuid4()).split('-')[0].upper()
        super().save_model(request, obj, form, change)

    def display_attributes(self, obj):
        attributes = obj.attributes.all()
        attributes_str = ", ".join([f"{attr.attribute.name}: {attr.value}{attr.unit}" for attr in attributes])
        return attributes_str

    display_attributes.short_description = 'Атрибуты'

    def image_preview(self, obj):
        first_image_url = obj.get_first_image_url()
        if first_image_url:
            return format_html('<img src="{}" style="width: 100px; height: auto;" />', first_image_url)
        return "Изображение не найдено"
    image_preview.short_description = 'Изображение'

    def __str__(self):
        return f"{self.product.name} - {self.sku}"
