from django.contrib import admin
from column_toggle.admin import ColumnToggleModelAdmin
from .models import Wheel, FAQ, Page, SocialLink
from django.utils.safestring import mark_safe
from django.utils.html import format_html

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

@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "column", "order", "is_published")
    list_filter = ("column", "is_published")
    search_fields = ("title", "slug", "body")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(SocialLink)
class SocialLinkAdmin(admin.ModelAdmin):
    list_display = ("title", "url", "order", "icon_tag")
    list_editable = ("order",)
    search_fields = ("title", "url")
    ordering = ("order", "title")
    readonly_fields = ("icon_preview",)
    fields = ("title", "url", "icon", "order", "icon_preview")

    def icon_tag(self, obj):
        if not obj.icon:
            return "—"
        return format_html(
            '<img src="{}" style="height:24px;width:24px;object-fit:contain;border-radius:4px;" />',
            obj.icon.url,
        )
    icon_tag.short_description = "Иконка"

    def icon_preview(self, obj):
        if not obj.icon:
            return "—"
        return format_html(
            '<img src="{}" style="max-height:120px;object-fit:contain;border:1px solid #eee;padding:4px;border-radius:6px;" />',
            obj.icon.url,
        )
    icon_preview.short_description = "Предпросмотр"