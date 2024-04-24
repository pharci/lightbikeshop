from django.contrib import admin
from django.db import models
from .models import *

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 1
    fields = ('product_variant', 'count')

class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'session_key', 'updated', 'created', 'get_cart_total_price', 'get_cart_total_count')
    inlines = [CartItemInline]
    search_fields = ('user__email', 'session_key')
    list_filter = ('created', 'updated')
    readonly_fields = ('get_cart_total_price', 'get_cart_total_count')

    def get_cart_total_price(self, obj):
        return obj.get_cart_total_price()
    get_cart_total_price.short_description = 'Общая стоимость'

    def get_cart_total_count(self, obj):
        return obj.get_cart_total_count()
    get_cart_total_count.short_description = 'Общее количество товаров'

admin.site.register(Cart, CartAdmin)

class PromotionAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_percentage', 'valid_from', 'valid_until', 'active', 'is_currently_valid')
    list_filter = ('active', 'valid_from', 'valid_until')
    search_fields = ('code', 'description')
    list_editable = ('active', 'discount_percentage')

    def is_currently_valid(self, obj):
        return obj.is_valid()
    is_currently_valid.boolean = True
    is_currently_valid.short_description = 'Текущая валидность'

admin.site.register(Promotion, PromotionAdmin)