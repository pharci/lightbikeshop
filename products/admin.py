from django.contrib import admin
from django.utils.html import format_html
from column_toggle.admin import ColumnToggleModelAdmin
from .models import *


admin.site.register(Category)
admin.site.register(Brand)

@admin.register(Product)
class ProductAdmin(ColumnToggleModelAdmin):
    list_display = ('image_preview', 'name', 'slug', 'price', 'all_count', 'light_inventory', 'mightbe_inventory', 'availability_status', 'category', 'brand',   'new', 'rec', 'description', 'created', 'updated')
    default_selected_columns = ['image_preview', 'name', 'price', 'all_count', 'light_inventory', 'mightbe_inventory', 'availability_status', 'category', 'brand']
    list_editable = ('name', 'slug', "price", "light_inventory", 'mightbe_inventory', 'availability_status')
    search_fields = ("slug", "name")
    list_filter = ('category', 'brand')

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 75px; max-width: 75px;" />', obj.image.url)
        return "None"
    image_preview.short_description = "Фото"

    def all_count(self, obj):
        return obj.mightbe_inventory + obj.light_inventory
    all_count.short_description = "Всего"