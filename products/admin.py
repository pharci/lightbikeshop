# admin.py
from django.contrib import admin
from django.utils.html import format_html
from column_toggle.admin import ColumnToggleModelAdmin
from adminsortable2.admin import SortableInlineAdminMixin, SortableAdminBase 

from .models import (
    Category, Brand, Attribute, CategoryAttribute,
    Product, Variant, Image, AttributeValue
)

# ---------- helpers ----------

def thumb(url, size=75):
    if not url:
        return format_html(
            '<div style="width:{s}px;height:{s}px;border-radius:8px;background:#f9f9f9;'
            'display:flex;align-items:center;justify-content:center;color:#999;'
            'font-size:12px;border:1px solid #ddd;">–</div>', s=size
        )
    return format_html(
        '<div style="width:{s}px;height:{s}px;overflow:hidden;border-radius:8px;'
        'background:#f9f9f9;display:flex;align-items:center;justify-content:center;border:1px solid #ddd;">'
        '<img src="{}" style="max-width:100%;max-height:100%;object-fit:contain"/></div>',
        url, s=size
    )

def pill(text, bg="#f3f4f6", br="#e5e7eb", fg="#374151"):
    return format_html(
        '<span style="background:{};border:1px solid {};color:{};'
        'padding:2px 8px;border-radius:999px;font-size:11px;">{}</span>',
        bg, br, fg, text
    )

# ---------- Inlines ----------

class ImageInline(SortableInlineAdminMixin, admin.TabularInline):
    model = Image
    extra = 0
    fields = ("preview", "image", "alt", "sort")
    readonly_fields = ("preview",)
    sortable = "sort"  # ← какое поле хранит порядок

    def preview(self, obj):
        url = obj.image.url if obj and obj.image else None
        return thumb(url, 60)
    preview.short_description = "Фото"


class CategoryAttributeInline(SortableInlineAdminMixin, admin.TabularInline):
    model = CategoryAttribute
    extra = 0
    fields = ("attribute", "is_required", "is_filterable", "is_variant", "sort_order")
    autocomplete_fields = ("attribute",)
    sortable = "sort_order"

class AttributeValueInline(admin.TabularInline):
    model = AttributeValue
    extra = 0
    fields = ("attribute", "value_text", "value_number", "value_bool")
    autocomplete_fields = ("attribute",)

class VariantInline(admin.TabularInline):
    model = Variant
    extra = 0
    fields = ("sku", "price", "inventory", "new", "rec")
    show_change_link = True

# ---------- Category ----------

@admin.register(Category)
class CategoryAdmin(SortableAdminBase, ColumnToggleModelAdmin):
    list_display = ("image_preview", "name", "second_name", "slug", "attributes_col", "parent", "image")
    default_selected_columns = ["image_preview", "name", "attributes_col"]
    list_display_links = ("image_preview",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [CategoryAttributeInline]  # атрибуты инлайном
    
    list_editable = ("image", "name", "second_name", "slug", "parent")

    def image_preview(self, obj):
        url = obj.image.url if obj.image else None
        return thumb(url)
    image_preview.short_description = "Фото"

    def attributes_col(self, obj: Category):
        """
        Список всех атрибутов категории c мини-бейджами флагов (req/filter/variant).
        """
        items = []
        # берём связанные CategoryAttribute в нужном порядке
        for ca in obj.category_attributes.select_related("attribute").order_by("sort_order", "id"):
            flags = []
            if ca.is_required:   flags.append(pill("req", "#eef2ff", "#c7d2fe", "#4338ca"))
            if ca.is_filterable: flags.append(pill("filter", "#ecfeff", "#a5f3fc", "#0e7490"))
            if ca.is_variant:    flags.append(pill("variant", "#f0fdf4", "#bbf7d0", "#16a34a"))
            flags_html = format_html(" ".join(str(f) for f in flags)) if flags else ""
            items.append(format_html(
                '<span style="display:inline-flex;align-items:center;gap:6px;'
                'border:1px solid #e5e7eb;border-radius:999px;padding:2px 10px;'
                'margin:2px;background:#f9fafb;">'
                '<strong style="font-weight:600;">{name}</strong>{flags}'
                '</span>',
                name=ca.attribute.name,
                flags=flags_html
            ))
        if not items:
            return "—"
        # компактный wrap
        return format_html('<div style="display:flex;flex-wrap:wrap;gap:6px;max-width:980px;">{}</div>', format_html("".join(items)))
    attributes_col.short_description = "Атрибуты"

# ---------- Brand ----------

@admin.register(Brand)
class BrandAdmin(ColumnToggleModelAdmin):
    list_display = ("image_preview", "title", "slug", "image")
    default_selected_columns = ["image_preview", "title"]
    list_display_links = ("image_preview",)
    search_fields = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}

    list_editable = ("image", "title", "slug")

    def image_preview(self, obj):
        url = obj.image.url if obj.image else None
        return thumb(url)
    image_preview.short_description = "Логотип"

# ---------- Attribute ----------

@admin.register(Attribute)
class AttributeAdmin(ColumnToggleModelAdmin):
    list_display = ("name", "slug", "value_type", "unit")
    default_selected_columns = ["name", "value_type"]
    search_fields = ("name", "slug")
    list_filter = ("value_type",)
    prepopulated_fields = {"slug": ("name",)}

# ---------- Product ----------

@admin.register(Product)
class ProductAdmin(ColumnToggleModelAdmin):
    """
    SPU: превью берем из первого изображения первого варианта.
    """
    list_display = ("image_preview", "base_name", "external_id", "slug", "category", "brand", "variants_count", "created", "updated")
    default_selected_columns = ["image_preview", "base_name", "category", "brand", "variants_count"]
    list_display_links = ("image_preview",)
    list_filter = ("category", "brand", "created", "updated")
    search_fields = ("base_name", "slug", "brand__title", "external_id")
    prepopulated_fields = {"slug": ("base_name",)}
    inlines = [VariantInline]
    list_editable = ("base_name", "category", "brand", "slug")  # ← можно менять прямо в таблице

    def variants_count(self, obj):
        return obj.variants.count()
    variants_count.short_description = "SKU"

    def image_preview(self, obj):
        first_variant = obj.variants.first()
        img = first_variant.images.first().image if (first_variant and first_variant.images.first()) else None
        url = img.url if img else None
        return thumb(url)
    image_preview.short_description = "Фото"

# ---------- Variant ----------

@admin.register(Variant)
class VariantAdmin(SortableAdminBase, ColumnToggleModelAdmin):
    list_display = (
        "image_preview", "display_name_col", "external_id", "sku", "price",
        "inventory", "new", "rec", "updated"
    )
    default_selected_columns = ["image_preview", "display_name_col", "price", "inventory"]
    list_display_links = ("display_name_col",)  # редактируемые поля не должны быть ссылками
    list_filter = ("new", "rec", "updated", "product__category", "product__brand")
    search_fields = ("sku", "product__base_name", "product__brand__title", "external_id")
    autocomplete_fields = ("product",)
    inlines = [ImageInline, AttributeValueInline]
    ordering = ("-updated",)

    # РЕДАКТИРОВАНИЕ В СПИСКЕ
    list_editable = ("price", "inventory", )  # ← можно менять прямо в таблице

    def display_name_col(self, obj):
        return obj.display_name() if hasattr(obj, "display_name") else str(obj)
    display_name_col.short_description = "Вариант"

    def image_preview(self, obj):
        url = obj.images.first().image.url if obj.images.first() and obj.images.first().image else obj.product.imageURL
        return thumb(url)
    image_preview.short_description = "Фото"

# ---------- AttributeValue ----------

@admin.register(AttributeValue)
class AttributeValueAdmin(ColumnToggleModelAdmin):
    list_display = ("variant", "attribute", "display_value")
    default_selected_columns = ["variant", "attribute", "display_value"]
    search_fields = ("variant__product__base_name", "variant__sku", "attribute__name", "value_text")
    list_filter = ("attribute__value_type",)
    autocomplete_fields = ("variant", "attribute")

# ---------- CategoryAttribute ----------
@admin.register(CategoryAttribute)
class CategoryAttributeAdmin(admin.ModelAdmin):
    list_display = (
        "category", "attribute",
        "is_required", "is_filterable", "is_variant",
        "sort_order",
    )
    list_editable = ("is_required", "is_filterable", "is_variant", "sort_order")
    list_filter = ("category", "is_required", "is_filterable", "is_variant")
    search_fields = ("category__name", "attribute__name", "attribute__slug")
    autocomplete_fields = ("category", "attribute")
    ordering = ("category__name", "sort_order", "id")


@admin.register(Image)
class ImageAdmin(SortableAdminBase, ColumnToggleModelAdmin):
    list_display = ("image_preview", "variant", "alt", "sort", "image")
    default_selected_columns = list(list_display)
    list_display_links = ("image_preview",)
    search_fields = ("variant", )
    list_editable = ("alt", "sort", "image")

    def image_preview(self, obj):
        url = obj.image.url if obj.image else None
        return thumb(url)
    image_preview.short_description = "Фото"