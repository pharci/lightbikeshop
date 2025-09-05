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
    fields = ("variant", "price", "quantity", "amount")
    readonly_fields = ("line_total",)
    raw_id_fields = ("variant",)


@admin.register(Order)
class OrderAdmin(ColumnToggleModelAdmin):
    """
    Заказы: превью, визитка, статус, деньги, промо, дата.
    """
    list_display = (
        "image_preview", "identity", "ms_order_id", "status_badge",
        "money_summary", "promo_badge", "date_ordered",
    )
    default_selected_columns = list(list_display)
    list_display_links = ("image_preview",)
    list_filter = ("status", "payment_type", "date_ordered")
    search_fields = ("order_id", "user_name", "contact_phone", "user__email")
    ordering = ("-date_ordered",)
    date_hierarchy = "date_ordered"
    inlines = [OrderItemInline]

    # readonly: промокод по-прежнему read-only (если нужно редактировать — убери)
    readonly_fields = ("date_ordered", "promo_code")

    fieldsets = (
        ("Основное", {
            "fields": ("user", "status", "user_name", "contact_phone", "email", "order_notes")
        }),
        ("Суммы и оплата", {
            "fields": ("subtotal", "discount_total", "shipping_total", "total", "payment_type", "payment_url")
        }),
        ("Получение/доставка", {
            "fields": ("pvz_code", "pvz_address")
        }),
        ("Промокод", {
            "fields": ("promo_code",)
        }),
        ("Служебное", {
            "fields": ("date_ordered",),
        }),
    )

    # ===== Виртуальные колонки =====
    @admin.display(description="Итого / состав", ordering="total")
    def money_summary(self, obj: Order):
        def fmt(x):
            return f"{x:,.0f}".replace(",", " ")
        return format_html(
            """
            <div style="line-height:1.4;font-size:13px;">
            <div><strong>Итого:</strong> ₽{total}</div>
            <div style="color:#374151;"><small>Без скидок:</small> ₽{subtotal}</div>
            <div style="color:#b91c1c;"><small>Скидка:</small> -₽{discount}</div>
            <div style="color:#0369a1;"><small>Доставка:</small> ₽{shipping}</div>
            </div>
            """,
            total=fmt(obj.total),
            subtotal=fmt(obj.subtotal),
            discount=fmt(obj.discount_total),
            shipping=fmt(obj.shipping_total),
        )

    @admin.display(description="Промокод")
    def promo_badge(self, obj: Order):
        if not obj.promo_code:
            return "—"
        code = obj.promo_code.code
        disc = obj.discount_total
        return format_html(
            "<span style='display:inline-flex;gap:6px;align-items:center;"
            "padding:2px 8px;border:1px solid #e7e9ee;border-radius:999px;"
            "background:#f7f8fa;'>{}<strong>− ₽{}</strong></span>",
            code, f"{disc:,.2f}".replace(",", " ")
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
        phone = obj.contact_phone or ""
        email = obj.email or ""
        user_chip = ""
        if obj.user_id and obj.user:
            user_chip = format_html(
                '<span style="margin-left:6px;padding:2px 6px;'
                'background:#eef2ff;border:1px solid #c7d2fe;'
                'color:#4338ca;border-radius:6px;font-size:11px;">{}</span>',
                obj.user,
            )

        return format_html(
            """
            <div style="line-height:1.4;font-size:13px;">
            <div style="font-weight:600;font-size:14px;margin-bottom:2px;">
                Заказ #{} {}
            </div>
            <div style="color:#111827;">{}</div>
            {}
            <div style="color:#6b7280;font-size:12px;">{}</div>
            </div>
            """,
            obj.order_id,
            format_html(user_chip),
            who,
            format_html('<div style="color:#374151;font-size:12px;">{}</div>', phone) if phone else "",
            email,
        )
    identity.short_description = "Визитка"

    # Бейдж статуса
    def status_badge(self, obj: Order):
        colors = {
            "created":   ("#eef2ff", "#c7d2fe", "#4338ca"),  # Новый
            "paid":      ("#ecfdf5", "#6ee7b7", "#047857"),  # Оплачен (зелёный ярче)
            "assembled": ("#fefce8", "#fde68a", "#92400e"),  # Собран (жёлтый)
            "shipped":   ("#eff6ff", "#bfdbfe", "#1d4ed8"),  # Отправлен (синий)
            "delivered": ("#f0fdf4", "#bbf7d0", "#166534"),  # Доставлен (тёмно-зелёный)
            "canceled":  ("#fef2f2", "#fecaca", "#b91c1c"),  # Отменён (красный)
        }
        bg, br, fg = colors.get(obj.status, ("#f3f4f6", "#e5e7eb", "#374151"))
        label = dict(Order.STATUS_CHOICES).get(obj.status, obj.status)
        return format_html(
            '<span style="background:{};border:1px solid {};color:{};'
            'padding:2px 8px;border-radius:999px;font-size:11px;">{}</span>',
            bg, br, fg, label
        )
    status_badge.short_description = "Статус"


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
