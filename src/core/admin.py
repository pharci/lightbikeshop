from django.contrib import admin
from django.utils.html import format_html

from column_toggle.admin import ColumnToggleModelAdmin

from .models import SocialLink, Wheel, FAQ, Page


@admin.register(SocialLink)
class SocialLinkAdmin(ColumnToggleModelAdmin, admin.ModelAdmin):
    list_display = ("icon_thumb", "order", "title", "url")
    default_selected_columns = list(list_display)
    list_display_links = ("icon_thumb", )
    list_editable = ("order", "title", "url", "order", "title")
    search_fields = ("title", "url")

    def icon_thumb(self, obj):
        if not obj.icon:
            return "—"
        return format_html('<img src="{}" class="adm-thumb" width="28" height="28" alt="{}">', obj.icon.url, obj.title)
    icon_thumb.short_description = "Иконка"


@admin.register(Wheel)
class WheelAdmin(ColumnToggleModelAdmin, admin.ModelAdmin):
    # добавлен raw-поле is_active для list_editable
    list_display = ("image_thumb", "order", "title", "is_active", )
    default_selected_columns = list(list_display)
    list_display_links = ("image_thumb", )
    list_editable = ("order", "title", "is_active")
    list_filter = ("is_active",)
    search_fields = ("title", "url")

    def image_thumb(self, obj):
        if not obj.image:
            return "—"
        return format_html('<img src="{}" class="adm-thumb" width="64" height="36" alt="{}">', obj.image.url, obj.title)
    image_thumb.short_description = "Превью"


@admin.register(FAQ)
class FAQAdmin(ColumnToggleModelAdmin, admin.ModelAdmin):
    list_display = ("id", "order", "title", "color_chip", "color", "is_active")
    default_selected_columns = list(list_display)
    list_display_links = ("id",)
    list_editable = ("order", "title", "color", "is_active")
    list_filter = ("is_active",)
    search_fields = ("title", "content", "color")

    def color_chip(self, obj):
        return format_html('<span class="adm-chip">цвет: {}</span>', obj.color)
    color_chip.short_description = "Флажок"


@admin.register(Page)
class PageAdmin(ColumnToggleModelAdmin, admin.ModelAdmin):
    list_display = ("id", "order", "title", "slug", "column", "is_published", "external_url", "anchor")
    default_selected_columns = list(list_display)
    list_display_links = ("id",)
    list_editable = ("order", "title", "slug", "column", "is_published", "external_url", "anchor")
    list_filter = ("column", "is_published")
    search_fields = ("title", "slug", "external_url", "anchor")
    prepopulated_fields = {"slug": ("title",)}