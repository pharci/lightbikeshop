from django.contrib import admin
from .models import *
import nested_admin

class OrderPaymentInline(nested_admin.NestedTabularInline):
    model = OrderPayment
    extra = 1
    verbose_name = "Оплата"
    verbose_name_plural = "Оплата"


class ShippingMethodInline(nested_admin.NestedTabularInline):
    model = ShippingMethod
    extra = 1
    verbose_name = "Способ получения"
    verbose_name_plural = "Способ получения"

class OrderItemInline(nested_admin.NestedTabularInline):
    model = OrderItem
    extra = 1
    verbose_name = "Товары"
    verbose_name_plural = "Товар"


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'address_line', 'city')
    search_fields = ('user__username', 'city')
    list_filter = ('city', )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'user', 'status', 'updated', 'created') 
    list_filter = ('status', 'created')
    search_fields = ('order_id', 'user__username', 'contact_phone')
    readonly_fields = ('order_id', 'get_total_price', 'get_total_count', 'created', 'updated')
    inlines = [ShippingMethodInline, OrderPaymentInline, OrderItemInline]

    def get_total_price(self, obj):
        return obj.get_total_price()
    get_total_price.short_description = 'Общая стоимость'

    def get_total_count(self, obj):
        return obj.get_total_count()
    get_total_count.short_description = 'Общее количество товаров'

admin.site.register(OrderItem)