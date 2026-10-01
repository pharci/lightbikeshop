# admin.py
from django.contrib import admin
from django.utils.html import format_html
from column_toggle.admin import ColumnToggleModelAdmin
from adminsortable2.admin import SortableInlineAdminMixin, SortableAdminBase 
from django.contrib import admin, messages
from django.db import transaction
from django.conf import settings
from django.db.models import Prefetch

from .models import *

from products.integrations.ms import get, save_variant_images


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
    fields = ("attribute", "is_filterable", "is_variant", "sort_order")
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
    fields = ("id", "price", "inventory", "sales_unit", "fulfillment_type", "new", "rec")
    show_change_link = True

# ---------- Category ----------

@admin.register(Category)
class CategoryAdmin(SortableAdminBase, ColumnToggleModelAdmin):
    list_display = ("image_preview", "title", "title_plural", "title_singular", "slug", "attributes_col", "parent", "image")
    default_selected_columns = list(list_display)
    list_display_links = ("image_preview",)
    search_fields = ("title", "title_plural", "title_plural", "title_singular", "slug")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [CategoryAttributeInline]
    list_editable = ("title", "title_plural", "title_singular", "slug", "parent", "image")

    @admin.display(description="Фото")
    def image_preview(self, obj):
        url = obj.image.url if obj.image else None
        return thumb(url)

    @admin.display(description="Атрибуты")
    def attributes_col(self, obj: Category):
        items = []
        q = obj.category_attributes.select_related("attribute").order_by("sort_order", "id")
        for ca in q:
            flags = []
            if ca.is_filterable: flags.append(pill("filter", "#ecfeff", "#a5f3fc", "#0e7490"))
            if ca.is_variant:    flags.append(pill("variant", "#f0fdf4", "#bbf7d0", "#16a34a"))
            flags_html = format_html(" ".join(map(str, flags))) if flags else ""
            items.append(format_html(
                '<span style="display:inline-flex;align-items:center;gap:6px;'
                'border:1px solid #e5e7eb;border-radius:999px;padding:2px 10px;'
                'margin:2px;background:#f9fafb;"><strong>{}</strong>{}</span>',
                ca.attribute.name, flags_html
            ))
        if not items:
            return "—"
        return format_html('<div style="display:flex;flex-wrap:wrap;gap:6px;max-width:980px;">{}</div>',
                           format_html("".join(items)))

# ---------- Brand ----------

@admin.register(Brand)
class BrandAdmin(ColumnToggleModelAdmin):
    list_display = ("image_preview", "title", "slug", "image", "description")
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
    list_display = ("image_preview", "id", "base_name", "category", "brand", "weight", "created", "updated")
    default_selected_columns = list(list_display)
    list_display_links = ("image_preview", "id")
    list_filter = (
        ("category", admin.RelatedOnlyFieldListFilter),
        ("brand", admin.RelatedOnlyFieldListFilter),
        "created", "updated",
    )
    search_fields = ("base_name", "brand__title")
    inlines = [VariantInline, AttributeValueInline]
    list_editable = ("base_name", "category", "brand", "weight")
    list_select_related = ("category", "brand")
    actions = ("action_refresh_photos", "import_all_products", )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "category", "brand"
        ).prefetch_related(
            Prefetch(
                "variants",
                queryset=Variant.objects.only("id", "product_id").order_by("created"),
                to_attr="prefetched_variants",
            ),
            Prefetch(
                "variants__images",
                queryset=Image.objects.only("id", "variant_id", "image", "sort").order_by("sort"),
                to_attr="prefetched_images",  # будет на каждом Variant
            ),
        )

    @admin.display(description="Фото")
    def image_preview(self, obj: Product):
        vlist = getattr(obj, "prefetched_variants", []) or []
        # первый вариант
        v = vlist[0] if vlist else None
        url = ""
        if v:
            imgs = getattr(v, "prefetched_images", []) or []
            if imgs:
                f = imgs[0]
                url = f.image.url if getattr(f, "image", None) else ""
        if not url:
            url = obj.imageURL or ""
        if not url:
            return "—"
        return format_html('<img src="{}" style="height:48px;width:auto;border-radius:4px;">', url)
    
    @admin.action(description="Обновить фотографии")
    def action_refresh_photos(self, request, queryset):
        updated = 0
        errors = 0
        for product in queryset:
            for variant in product.variants.all():
                try:
                    with transaction.atomic():
                        url = f"{settings.MOYSKLAD_BASE}/entity/variant/{variant.id}"
                        data = get(url, params={"expand": "images"})
                        save_variant_images(variant, data.get("images") or {})
                        updated += 1
                except Exception as e:
                    errors += 1
        if updated:
            messages.success(request, f"Фото обновлены у {updated} вариант(ов).")
        if errors:
            messages.error(request, f"Ошибок: {errors}.")
# ---------- Variant ----------

@admin.register(Variant)
class VariantAdmin(SortableAdminBase, ColumnToggleModelAdmin):
    list_display = (
        "image_preview", "id", "display_name_col", "slug",
        "seller_article", "ozon_article", "wb_article", "price", "old_price",
        "inventory", "fulfillment_type", "preorder_variant", "new", "rec", "is_active", "updated",
    )
    default_selected_columns = list(list_display)
    list_display_links = ("image_preview", "id", "display_name_col")
    list_filter = (
        "new", "rec", "is_active", "updated",
        ("product__category", admin.RelatedOnlyFieldListFilter),
        ("product__brand", admin.RelatedOnlyFieldListFilter),
    )
    search_fields = ("slug", "id", "seller_article", "product__base_name")
    autocomplete_fields = ("product", "preorder_variant")
    inlines = [ImageInline, AttributeValueInline]
    ordering = ("-updated",)
    list_editable = ("old_price", "price", "inventory", "new", "rec", "is_active")
    list_per_page = 50
    date_hierarchy = "updated"
    preserve_filters = True
    empty_value_display = "—"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Нужны product, brand, category для display_name(); images для превью
        return qs.select_related(
            "product", "product__brand", "product__category"
        ).prefetch_related(
            Prefetch(
                "images",
                queryset=Image.objects.only("id", "variant_id", "image", "sort").order_by("sort"),
                to_attr="prefetched_images",
            )
        )

    @admin.display(description="Вариант", ordering="slug")
    def display_name_col(self, obj: Variant):
        return str(obj)  # использует Variant.__str__ → display_name()

    @admin.display(description="Фото")
    def image_preview(self, obj: Variant):
        # сначала берём из prefetched_images, иначе main_image_url()
        url = None
        imgs = getattr(obj, "prefetched_images", None)
        if imgs:
            im0 = imgs[0]
            url = im0.image.url if getattr(im0, "image", None) else None
        if not url:
            return "—"
        return format_html('<img src="{}" style="height:48px;width:auto;border-radius:4px;">', url)


class CatalogVariantAdmin(VariantAdmin):
    list_display = (
        "catalog_image", "product_summary", "price_summary",
        "availability_summary", "source_shop", "storefront_link", "updated",
    )
    default_selected_columns = list(list_display)
    list_display_links = ("catalog_image", "product_summary")
    list_filter = (
        "is_active", "new", "rec",
        ("product__category", admin.RelatedOnlyFieldListFilter),
        ("product__brand", admin.RelatedOnlyFieldListFilter),
    )
    list_editable = ()
    date_hierarchy = None
    ordering = ("product__brand__title", "product__base_name")

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related(
            Prefetch(
                "taobao_imports",
                queryset=TaobaoImportItem.objects.only("id", "variant_id", "store", "updated_at").order_by("-updated_at"),
                to_attr="admin_imports",
            )
        )

    @admin.display(description="Фото")
    def catalog_image(self, obj):
        imgs = getattr(obj, "prefetched_images", None) or []
        url = imgs[0].image.url if imgs and imgs[0].image else obj.main_image_url()
        return thumb(url, 76)

    @admin.display(description="Товар", ordering="product__base_name")
    def product_summary(self, obj):
        brand = obj.product.brand.title if obj.product.brand else "Без бренда"
        category = obj.product.category.title_singular or obj.product.category.title
        return format_html(
            '<div style="min-width:260px;line-height:1.4">'
            '<strong style="font-size:14px;color:#111827">{}</strong>'
            '<div style="margin-top:5px;display:flex;gap:5px;flex-wrap:wrap">'
            '<span style="padding:2px 7px;border-radius:999px;background:#eef2ff;color:#4338ca;font-size:11px">{}</span>'
            '<span style="padding:2px 7px;border-radius:999px;background:#f3f4f6;color:#4b5563;font-size:11px">{}</span>'
            '</div></div>',
            obj.display_name(), brand, category,
        )

    @admin.display(description="Цена", ordering="price")
    def price_summary(self, obj):
        old = format_html('<div style="color:#9ca3af;text-decoration:line-through;font-size:11px">{} ₽</div>', f"{obj.old_price:,.0f}".replace(",", " ")) if obj.old_price else ""
        return format_html(
            '<div style="white-space:nowrap"><strong style="font-size:16px;color:#111827">{} ₽</strong>{}</div>',
            f"{obj.price:,.0f}".replace(",", " "), old,
        )

    @admin.display(description="Статус")
    def availability_summary(self, obj):
        if obj.is_preorder:
            return format_html(
                '<div style="padding:7px 10px;border-radius:9px;background:#f5f3ff;color:#6d28d9;white-space:nowrap">'
                '<strong>Под заказ</strong><br><small>{}–{} дней</small></div>',
                obj.preorder_days_min, obj.preorder_days_max,
            )
        if obj.inventory:
            return format_html(
                '<div style="padding:7px 10px;border-radius:9px;background:#ecfdf5;color:#047857;white-space:nowrap">'
                '<strong>В наличии</strong><br><small>{} {}</small></div>',
                obj.inventory, obj.sales_unit_label,
            )
        return format_html(
            '<div style="padding:7px 10px;border-radius:9px;background:#fef2f2;color:#b91c1c;white-space:nowrap">'
            '<strong>Закончился</strong><br><small>0 {}</small></div>', obj.sales_unit_label,
        )

    @admin.display(description="Источник")
    def source_shop(self, obj):
        imports = getattr(obj, "admin_imports", [])
        if not imports:
            return pill("Склад", "#f3f4f6", "#e5e7eb", "#374151")
        store = imports[0].store or "Taobao"
        color = ("#eff6ff", "#bfdbfe", "#1d4ed8") if "touch" in store.lower() else ("#faf5ff", "#e9d5ff", "#7e22ce")
        return pill(store, *color)

    @admin.display(description="На сайте")
    def storefront_link(self, obj):
        return format_html('<a href="{}" target="_blank" style="white-space:nowrap">Открыть ↗</a>', obj.get_absolute_url())


@admin.register(StockVariant)
class StockVariantAdmin(CatalogVariantAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(fulfillment_type=Variant.FulfillmentType.STOCK)


@admin.register(PreorderVariant)
class PreorderVariantAdmin(CatalogVariantAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(fulfillment_type=Variant.FulfillmentType.PREORDER)
# ---------- AttributeValue ----------

@admin.register(AttributeValue)
class AttributeValueAdmin(ColumnToggleModelAdmin):
    list_display = ("product", "variant", "attribute", "display_value")
    default_selected_columns = ["variant", "attribute", "display_value"]
    search_fields = ("variant__product__base_name", "attribute__name", "value_text")
    list_filter = ("attribute__value_type",)
    autocomplete_fields = ("variant", "attribute")
    list_display_links = ("product", "variant")

# ---------- CategoryAttribute ----------
@admin.register(CategoryAttribute)
class CategoryAttributeAdmin(admin.ModelAdmin):
    list_display = (
        "category", "attribute",
        "is_filterable", "is_variant",
        "sort_order",
    )
    list_editable = ("is_filterable", "is_variant", "sort_order")
    list_filter = ("category", "is_filterable", "is_variant")
    search_fields = ("category__title", "attribute__name", "attribute__slug")
    autocomplete_fields = ("category", "attribute")
    ordering = ("category__title", "sort_order", "id")


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


@admin.register(RelatedVariant)
class RelatedVariantAdmin(admin.ModelAdmin):
    list_display = ("from_variant","to_variant","source","weight","pinned","position","is_active")
    list_filter  = ("source","is_active","pinned")
    search_fields = ("from_variant__id","to_variant__id",
                     "from_variant__product__base_name","to_variant__product__base_name")
    autocomplete_fields = ("from_variant","to_variant")
    ordering = ("-pinned","-weight","position","id")

@admin.register(CopurchaseVariantStat)
class CopurchaseVariantStatAdmin(admin.ModelAdmin):
    list_display = ("variant_min","variant_max","count","last_seen")


@admin.register(TaobaoImportItem)
class TaobaoImportItemAdmin(admin.ModelAdmin):
    list_display = ("image_preview", "title_ru", "store", "brand_name", "category_name", "variant_name", "price_rub", "available", "status", "updated_at")
    list_filter = ("status", "store", "available", "category_name", "brand_name")
    search_fields = ("title_ru", "title_original", "external_id", "brand_name")
    readonly_fields = ("source_key", "external_id", "store", "title_original", "image_preview", "product_url", "received_at", "updated_at", "raw")
    list_editable = ("status",)
    autocomplete_fields = ("product", "variant")

    @admin.display(description="Фото")
    def image_preview(self, obj):
        return thumb(obj.image_url, 64)
