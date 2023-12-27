from django.contrib import admin
from .models import *


admin.site.register(CartItem)

class CartItemInline(admin.TabularInline):
    model = CartItem
    raw_id_fields = ['product']
    extra = 0


class CartAdmin(admin.ModelAdmin):
    inlines = [CartItemInline]

admin.site.register(Cart, CartAdmin)