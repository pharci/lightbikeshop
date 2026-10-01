from django import forms
from django.conf import settings
from django.contrib import admin
from django.core.cache import cache
from django.utils.html import format_html

from column_toggle.admin import ColumnToggleModelAdmin

from .models import SocialLink, Wheel, FAQ, Page, IntegrationKey


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


class IntegrationKeyForm(forms.ModelForm):
    value = forms.CharField(
        label="Ключ / значение",
        required=False,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
        help_text="Введите новое значение. Оставьте пустым, чтобы сохранить текущее.",
    )

    class Meta:
        model = IntegrationKey
        fields = ("key", "value")

    def clean_value(self):
        value = self.cleaned_data.get("value", "").strip()
        if not self.instance.pk and not value and not getattr(settings, self.cleaned_data.get("key", ""), ""):
            raise forms.ValidationError("Введите значение ключа.")
        return value

    def save(self, commit=True):
        obj = super().save(commit=False)
        value = self.cleaned_data.get("value")
        if value:
            obj.set_value(value)
        if commit:
            obj.save()
        return obj


@admin.register(IntegrationKey)
class IntegrationKeyAdmin(admin.ModelAdmin):
    form = IntegrationKeyForm
    list_display = ("key_title", "configured", "source", "updated_at")
    search_fields = ("key",)
    readonly_fields = ("updated_at",)

    def get_readonly_fields(self, request, obj=None):
        return ("key", "updated_at") if obj else ("updated_at",)

    def has_add_permission(self, request):
        return (
            super().has_add_permission(request)
            and IntegrationKey.objects.count() < len(IntegrationKey.KEY_CHOICES)
        )

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Интеграция", ordering="key")
    def key_title(self, obj):
        return obj.get_key_display()

    @admin.display(description="Состояние", boolean=True)
    def configured(self, obj):
        return bool(obj.get_value() or getattr(settings, obj.key, ""))

    @admin.display(description="Источник")
    def source(self, obj):
        return "Админка" if obj.get_value() else ("Переменные окружения" if getattr(settings, obj.key, "") else "Не настроено")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        cache.delete(f"integration-key:{obj.key}")
