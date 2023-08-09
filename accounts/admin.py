from django.contrib import admin
from django.urls import reverse
# Register your models here.
from .models import *

admin.site.register(User)
admin.site.register(OrderItem)

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ['product']
    extra = 0


class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    list_display = ('order_id', 'status')
    list_filter = ('status',)
    search_fields = ('order_id', )

admin.site.register(Order, OrderAdmin)