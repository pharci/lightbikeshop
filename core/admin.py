from django.contrib import admin
from column_toggle.admin import ColumnToggleModelAdmin
from .models import Wheel, FAQ
from django.utils.safestring import mark_safe

@admin.register(Wheel)
class WheelAdmin(ColumnToggleModelAdmin):
    list_display = ("image_preview", "title", "order", "is_active", "url", 'image')
    default_selected_columns = list(list_display),
    list_editable = ("image", "url", "order", "is_active")
    list_display_links = ("image_preview", "title")
    search_fields = ("title",)
    ordering = ("order",)
    list_per_page = 30

    def image_preview(self, obj):
        if obj.image:
            return mark_safe(f'<img src="{obj.image.url}" style="height:100px;" />')
        return "-"
    

@admin.register(FAQ)
class FAQAdmin(ColumnToggleModelAdmin):
    list_display = ("title", "order", "is_active", "color")
    default_selected_columns = list(list_display),
    list_editable = ("order", "is_active", "color")
    search_fields = ("title", "content")
    ordering = ("order",)