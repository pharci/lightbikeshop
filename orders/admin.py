from django.contrib import admin
from .models import *

@admin.register(OrderStatus)
class OrderStatusAdmin(admin.ModelAdmin):
    list_display = ('status', 'description')

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'address_line', 'city', 'postal_code', 'country')
    search_fields = ('user__username', 'city', 'postal_code')
    list_filter = ('city', 'country')

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'user', 'status', 'receiving_method', 'delivery_method', 'updated', 'created')
    inlines = [OrderItemInline]
    list_filter = ('status', 'receiving_method', 'delivery_method', 'created')
    search_fields = ('order_id', 'user__username', 'contact_phone')
    readonly_fields = ('order_id', 'get_total_price', 'get_total_count', 'created', 'updated')

    def get_total_price(self, obj):
        return obj.get_total_price()
    get_total_price.short_description = 'Общая стоимость'

    def get_total_count(self, obj):
        return obj.get_total_count()
    get_total_count.short_description = 'Общее количество товаров'

admin.site.register(OrderItem)

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