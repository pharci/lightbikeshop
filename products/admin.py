from django.contrib import admin
from .models import *

class ProductImageInline(admin.TabularInline):  # Или StackedInline, в зависимости от ваших предпочтений
    model = ProductImage

class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductImageInline]

admin.site.register(Product, ProductAdmin)
admin.site.register(ProductImage)
admin.site.register(Category)
admin.site.register(Brand)