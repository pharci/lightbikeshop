from __future__ import annotations

from decimal import Decimal

from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Cart, CartItem,
    Order, OrderItem,
    PickupPoint,
    PromoCode,
)

from column_toggle.admin import ColumnToggleModelAdmin


# ───────────────────────────── CART ───────────────────────────── #

@admin.register(CartItem)
class CartItemAdmin(ColumnToggleModelAdmin):
    list_display = ("cart", "variant", "quantity")
    default_selected_columns = list(list_display)
    search_fields = ("cart__user__email", "variant__sku", "variant__product__title")
    autocomplete_fields = ("cart", "variant")


class CartItemInline(admin.TabularInline):
    model = CartItem
    raw_id_fields = ['variant']
    extra = 0


@admin.register(Cart)
class CartAdmin(ColumnToggleModelAdmin):
    inlines = [CartItemInline]
    list_display = ("id", "user", "items_count", "total_price", "updated_at")
    default_selected_columns = list(list_display)
    search_fields = ("user__email",)
    list_select_related = ("user",)
    ordering = ("-updated_at",)

    def items_count(self, obj: Cart) -> int:
        return obj.get_total_items()
    items_count.short_description = "Товаров"

    def total_price(self, obj: Cart) -> Decimal:
        return obj.get_cart_total_price()
    total_price.short_description = "Сумма"


# ───────────────────────────── ORDERS ───────────────────────────── #

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ("variant", "price", "quantity", "line_total")
    readonly_fields = ("line_total",)
    raw_id_fields = ("variant",)

    def line_total(self, obj=None):
        if not obj or obj.pk is None:
            return ""
        price = Decimal(obj.price or 0)
        qty = int(obj.quantity or 0)
        return price * qty
    line_total.short_description = "Сумма"


@admin.register(Order)
class OrderAdmin(ColumnToggleModelAdmin):
    """
    Админка заказов: превью, визитка, бейджи статуса, промокод+скидка.
    """
    list_display = (
        "image_preview", "identity", "status_badge",
        "amount", "promo_badge",
        "date_ordered",
    )
    default_selected_columns = list(list_display)  # для ColumnToggle; игнорится обычной админкой
    list_display_links = ("identity",)
    list_filter = ("status", "date_ordered")
    search_fields = (
        "order_id", "user_name", "contact_phone",
        "user__email",
    )
    ordering = ("-date_ordered",)
    date_hierarchy = "date_ordered"
    inlines = [OrderItemInline]

    readonly_fields = ("date_ordered", "payment_id", "promo_code", "promo_discount_amount")

    fieldsets = (
        ("Основное", {
            "fields": ("user", "status", "user_name", "contact_phone", "email", "order_notes")
        }),
        ("Оплата", {
            "fields": ("amount", "payment_type", "payment_id")
        }),
        ("Получение/доставка", {
            "fields": ("city", "pvz_code", "pvz_address")
        }),
        ("Промокод", {
            "fields": ("promo_code", "promo_discount_amount")
        }),
        ("Служебное", {
            "fields": ("date_ordered",),
        }),
    )

    # Превью первой картинки
    def image_preview(self, obj: Order):
        item = obj.items.first()
        img = (item.variant.images.first().image if item and hasattr(item.variant, "images") else None)
        if img:
            return format_html(
                '<div style="width:75px;height:75px;overflow:hidden;border-radius:8px;'
                'background:#f9f9f9;display:flex;align-items:center;justify-content:center;border:1px solid #ddd;">'
                '<img src="{}" style="max-width:100%;max-height:100%;object-fit:contain"/></div>',
                img.url
            )
        return format_html(
            '<div style="width:75px;height:75px;border-radius:8px;background:#f9f9f9;'
            'display:flex;align-items:center;justify-content:center;color:#999;font-size:12px;border:1px solid #ddd;">–</div>'
        )
    image_preview.short_description = "Фото"

    # Визитка
    def identity(self, obj: Order):
        who = obj.user_name or "—"
        phone = f' · <span style="color:#6b7280">{obj.contact_phone}</span>' if obj.contact_phone else ""
        user_chip = ""
        if obj.user_id and obj.user:
            u = obj.user
            u_label = u.email or f"user#{u.pk}"
            user_chip = f'<span style="margin-left:8px;background:#f3f4f6;border:1px solid #e5e7eb;color:#374151;padding:1px 6px;border-radius:6px;font-size:11px;">{u_label}</span>'
        return format_html(
            '<div style="line-height:1.2;"><strong>Заказ #{}</strong><br/>{}{} {}</div>',
            obj.order_id, who, format_html(phone), format_html(user_chip)
        )
    identity.short_description = "Заказ"

    # Бейдж статуса
    def status_badge(self, obj: Order):
        colors = {
            "created":           ("#eef2ff", "#c7d2fe", "#4338ca"),
            "processing":        ("#fff7ed", "#fed7aa", "#c2410c"),
            "goes_to_point":     ("#ecfeff", "#a5f3fc", "#0e7490"),
            "ready_for_shipping":("#f0fdf4", "#bbf7d0", "#16a34a"),
            "shipped":           ("#eff6ff", "#bfdbfe", "#1d4ed8"),
            "completed":         ("#ecfdf5", "#a7f3d0", "#0f766e"),
            "canceled":          ("#fef2f2", "#fecaca", "#b91c1c"),
        }
        bg, br, fg = colors.get(obj.status, ("#f3f4f6", "#e5e7eb", "#374151"))
        label = dict(Order.STATUS_CHOICES).get(obj.status, obj.status)
        return format_html(
            '<span style="background:{};border:1px solid {};color:{};padding:2px 8px;border-radius:999px;font-size:11px;">{}</span>',
            bg, br, fg, label
        )
    status_badge.short_description = "Статус"

    def promo_badge(self, obj: Order):
        if not obj.promo_code_id:
            return "—"
        return format_html(
            '<span style="background:#ecfeff;border:1px solid #a5f3fc;color:#0e7490;'
            'padding:2px 8px;border-radius:999px;font-size:11px;">{} (−{} ₽)</span>',
            obj.promo_code.code, int(Decimal(obj.promo_discount_amount or 0))
        )
    promo_badge.short_description = "Промо"

    # Быстрые действия
    @admin.action(description="Пометить как 'В обработке'")
    def mark_processing(self, request, queryset):
        queryset.update(status="processing")

    @admin.action(description="Пометить как 'Отправлен'")
    def mark_shipped(self, request, queryset):
        queryset.update(status="shipped")

    @admin.action(description="Пометить как 'Готов к выдаче'")
    def mark_ready(self, request, queryset):
        queryset.update(status="ready_for_shipping")

    @admin.action(description="Пометить как 'Отменен'")
    def mark_canceled(self, request, queryset):
        queryset.update(status="canceled")

    @admin.action(description="Пометить как 'Завершен'")
    def mark_completed(self, request, queryset):
        queryset.update(status="completed")

    actions = ["mark_processing", "mark_shipped", "mark_ready", "mark_canceled", "mark_completed"]


# ───────────────────────────── PICKUP ───────────────────────────── #

@admin.register(PickupPoint)
class PickupPointAdmin(ColumnToggleModelAdmin):
    list_display = ("title", "city", "address", "schedule", "is_active", "sort")
    default_selected_columns = list(list_display)
    list_filter = ("city", "is_active")
    search_fields = ("title", "address", "city", "slug")
    ordering = ("city", "sort", "title")


# ───────────────────────────── PROMO ───────────────────────────── #

@admin.register(PromoCode)
class PromoCodeAdmin(ColumnToggleModelAdmin):
    list_display = (
        "code", "discount_type", "amount",
        "is_active", "period", "usage", "per_user_limit",
        "min_order_total", "updated_at",
    )
    default_selected_columns = list(list_display)
    list_filter = ("is_active", "discount_type")
    search_fields = ("code",)
    readonly_fields = ("used_count", "created_at", "updated_at")
    actions = ["activate", "deactivate"]

    fieldsets = (
        (None, {"fields": ("code", "is_active")}),
        ("Скидка", {"fields": ("discount_type", "amount")}),
        ("Ограничения", {"fields": ("min_order_total", "usage_limit", "per_user_limit")}),
        ("Период действия", {"fields": ("starts_at", "ends_at")}),
        ("Служебное", {"fields": ("used_count", "created_at", "updated_at")}),
    )

    def period(self, obj: PromoCode):
        start = obj.starts_at.strftime("%d.%m.%Y") if obj.starts_at else "—"
        end = obj.ends_at.strftime("%d.%m.%Y") if obj.ends_at else "—"
        return f"{start} → {end}"
    period.short_description = "Период"

    def usage(self, obj: PromoCode):
        if obj.usage_limit is None:
            return f"{obj.used_count} / ∞"
        return f"{obj.used_count} / {obj.usage_limit}"
    usage.short_description = "Использований"

    @admin.action(description="Активировать")
    def activate(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Деактивировать")
    def deactivate(self, request, queryset):
        queryset.update(is_active=False)
