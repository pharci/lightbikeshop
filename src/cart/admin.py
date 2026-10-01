from __future__ import annotations
from django.contrib.admin.utils import quote as admin_quote
from django.urls import reverse
from decimal import Decimal

from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import path
from django.utils.html import format_html
from django.utils import timezone
from cart.views.order import _get_payment_url

from .models import (
    Cart, CartItem,
    Order, OrderItem, PreorderPurchase,
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


def sync_preorder_status(order):
    items = list(order.items.filter(variant__fulfillment_type="preorder"))
    if not items:
        return
    statuses = {item.procurement_status for item in items}
    if statuses == {OrderItem.ProcurementStatus.COMPLETED}:
        status = "delivered"
    elif all(item.procurement_status in {OrderItem.ProcurementStatus.CDEK_TRANSIT, OrderItem.ProcurementStatus.COMPLETED} for item in items):
        status = "preorder_cdek_transit"
    elif all(item.procurement_status in {OrderItem.ProcurementStatus.AT_MIGHTBE, OrderItem.ProcurementStatus.CDEK_TRANSIT, OrderItem.ProcurementStatus.COMPLETED} for item in items):
        status = "preorder_arrived"
    elif all(item.procurement_status != OrderItem.ProcurementStatus.WAITING for item in items):
        status = "preorder_in_transit"
    else:
        status = "preorder_ordered"
    Order.objects.filter(pk=order.pk).update(status=status)


@admin.register(PreorderPurchase)
class PreorderPurchaseAdmin(admin.ModelAdmin):
    list_display = ("variant", "supplier_badge", "quantity", "order_link", "payment_badge", "customer", "procurement_status", "purchased_at", "eta")
    list_filter = ("supplier", "procurement_status", "order__status")
    search_fields = ("variant__product__base_name", "variant__product__brand__title", "order__order_id", "order__user_name")
    list_select_related = ("variant", "variant__product", "variant__product__brand", "variant__product__category", "order")
    readonly_fields = ("order", "variant", "price", "quantity", "amount", "purchased_at", "expected_delivery_from", "expected_delivery_to")
    fields = ("supplier", "procurement_status", "order", "variant", "quantity", "price", "amount", "purchased_at", "expected_delivery_from", "expected_delivery_to")
    actions = ("mark_purchased", "mark_at_mightbe", "mark_cdek_transit", "mark_completed")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            order__kind=Order.Kind.PREORDER,
            order__status__in=(
                "pending_confirmation", "preorder_confirmed", "paid",
                "preorder_ordered", "preorder_in_transit", "preorder_arrived",
                "preorder_cdek_transit", "delivered",
            ),
            variant__fulfillment_type="preorder",
        )

    @admin.display(description="Поставщик", ordering="supplier")
    def supplier_badge(self, obj):
        colors = {"touch": "#2563eb", "evo": "#7c3aed", "other": "#6b7280"}
        return format_html('<b style="color:{}">{}</b>', colors.get(obj.supplier, "#6b7280"), obj.get_supplier_display())

    @admin.display(description="Заказ")
    def order_link(self, obj):
        url = reverse("admin:cart_order_change", args=[admin_quote(obj.order_id)])
        return format_html('<a href="{}">#{}</a>', url, obj.order.order_id)

    @admin.display(description="Клиент")
    def customer(self, obj):
        return f"{obj.order.user_name} · {obj.order.contact_phone}"

    @admin.display(description="Оплата", ordering="order__status")
    def payment_badge(self, obj):
        paid_statuses = {
            "paid", "preorder_ordered", "preorder_in_transit",
            "preorder_arrived", "preorder_cdek_transit", "delivered",
        }
        if obj.order.status in paid_statuses:
            return format_html(
                '<strong style="padding:4px 8px;border-radius:999px;background:#dcfce7;color:#166534">Оплачен</strong>'
            )
        return format_html(
            '<strong style="padding:4px 8px;border-radius:999px;background:#fef3c7;color:#92400e">Ожидает оплаты</strong>'
        )

    @admin.display(description="Ожидаемая доставка")
    def eta(self, obj):
        if not obj.expected_delivery_from:
            return "—"
        return f"{obj.expected_delivery_from:%d.%m.%Y} – {obj.expected_delivery_to:%d.%m.%Y}"

    def _set_status(self, request, queryset, status, label):
        orders = set()
        count = 0
        skipped = 0
        for item in queryset:
            if status == OrderItem.ProcurementStatus.PURCHASED:
                if item.order.status in {"pending_confirmation", "preorder_confirmed"}:
                    skipped += 1
                    continue
                item.mark_purchased()
            else:
                item.procurement_status = status
                item.save(update_fields=["supplier", "procurement_status"])
            orders.add(item.order)
            count += 1
        for order in orders:
            sync_preorder_status(order)
        self.message_user(request, f"{label}: {count}")
        if skipped:
            self.message_user(request, f"Пропущено неоплаченных позиций: {skipped}", level=messages.WARNING)

    @admin.action(description="Заказал у поставщика")
    def mark_purchased(self, request, queryset):
        self._set_status(request, queryset, OrderItem.ProcurementStatus.PURCHASED, "Выкуплено")

    @admin.action(description="Приехал на склад MightBe")
    def mark_at_mightbe(self, request, queryset):
        self._set_status(request, queryset, OrderItem.ProcurementStatus.AT_MIGHTBE, "Приехало на MightBe")

    @admin.action(description="Передан в СДЭК — едет по России")
    def mark_cdek_transit(self, request, queryset):
        self._set_status(request, queryset, OrderItem.ProcurementStatus.CDEK_TRANSIT, "Передано в СДЭК")

    @admin.action(description="Доставлен клиенту")
    def mark_completed(self, request, queryset):
        self._set_status(request, queryset, OrderItem.ProcurementStatus.COMPLETED, "Доставлено")


@admin.register(Order)
class OrderAdmin(ColumnToggleModelAdmin):
    """
    Заказы: превью, визитка, статус, деньги, промо, дата.
    """
    list_display = (
        "image_preview", "identity", "kind", "storefront_link", "ms_order_id", "status_badge",
        "money_summary", "promo_badge", "date_ordered",
    )
    default_selected_columns = list(list_display)
    list_display_links = ("image_preview",)
    list_filter = ("kind", "status", "payment_type", "date_ordered")
    search_fields = ("order_id", "user_name", "contact_phone", "user__email")
    ordering = ("-date_ordered",)
    date_hierarchy = "date_ordered"
    inlines = [OrderItemInline]
    actions = ("confirm_preorders_and_create_payment",)

    @admin.action(description="Подтвердить под заказ и создать ссылку оплаты")
    def confirm_preorders_and_create_payment(self, request, queryset):
        created = errors = 0
        for order in queryset.filter(kind=Order.Kind.PREORDER, ms_order_id__isnull=True):
            try:
                order.admin_confirmed_at = timezone.now()
                order.status = "preorder_confirmed"
                order.save(update_fields=["admin_confirmed_at", "status"])
                _get_payment_url(order, request)
                created += 1
            except Exception:
                order.status = "pending_confirmation"
                order.admin_confirmed_at = None
                order.save(update_fields=["admin_confirmed_at", "status"])
                errors += 1
        if created:
            self.message_user(request, f"Подтверждено заказных товаров: {created}")
        if errors:
            self.message_user(request, f"Не удалось создать ссылку для {errors} заказов", level="error")

    # readonly: промокод по-прежнему read-only (если нужно редактировать — убери)
    readonly_fields = ("status_controls", "date_ordered", "promo_code")

    fieldsets = (
        ("Основное", {
            "fields": ("kind", "status_controls", "status", "admin_confirmed_at", "ms_order_id", "user", "user_name", "contact_phone", "email", "order_notes")
        }),
        ("Суммы и оплата", {
            "fields": ("subtotal", "discount_total", "shipping_total", "total", "payment_type", "payment_url")
        }),
        ("Получение/доставка", {
            "fields": ("city", "pvz_provider", "pvz_code", "pvz_address", "invoice")
        }),
        ("Промокод", {
            "fields": ("promo_code",)
        }),
        ("Служебное", {
            "fields": ("date_ordered",),
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "status" in form.base_fields:
            kind = obj.kind if obj else request.POST.get("kind", Order.Kind.STOCK)
            form.base_fields["status"].choices = (
                Order.PREORDER_STATUS_CHOICES
                if kind == Order.Kind.PREORDER
                else Order.STOCK_STATUS_CHOICES
            )
        return form

    def get_urls(self):
        custom = [
            path(
                "<path:object_id>/set-status/<str:status>/",
                self.admin_site.admin_view(self.set_status_view),
                name="cart_order_set_status",
            ),
        ]
        return custom + super().get_urls()

    def set_status_view(self, request, object_id, status):
        order = get_object_or_404(Order, pk=object_id)
        allowed = dict(order.allowed_status_choices())
        if request.method != "POST" or status not in allowed:
            self.message_user(request, "Этот статус не подходит для типа заказа.", level=messages.ERROR)
        else:
            order.status = status
            update_fields = ["status", "updated"]
            if order.kind == Order.Kind.PREORDER and status == "preorder_confirmed":
                order.admin_confirmed_at = timezone.now()
                update_fields.append("admin_confirmed_at")
            order.save(update_fields=update_fields)
            self.message_user(request, f"Статус изменён: {allowed[status]}.", level=messages.SUCCESS)
        return HttpResponseRedirect(reverse("admin:cart_order_change", args=[admin_quote(order.pk)]))

    @admin.display(description="Быстрая смена статуса")
    def status_controls(self, obj):
        if not obj or not obj.pk:
            return "Сначала сохраните заказ"
        buttons = []
        for value, label in obj.allowed_status_choices():
            url = reverse("admin:cart_order_set_status", args=[admin_quote(obj.pk), value])
            active = value == obj.status
            buttons.append(format_html(
                '<button type="submit" formaction="{}" formmethod="post" {} '
                'style="margin:0 6px 7px 0;padding:7px 11px;border-radius:8px;'
                'border:1px solid {};background:{};color:{};cursor:{};font-weight:600">{}</button>',
                url,
                "disabled" if active else "",
                "#2563eb" if active else "#d1d5db",
                "#2563eb" if active else "#fff",
                "#fff" if active else "#111827",
                "default" if active else "pointer",
                label,
            ))
        return format_html(
            '<div style="max-width:900px"><div style="margin-bottom:8px;color:#6b7280">'
            'Доступны только статусы для типа «{}». Кнопка меняет статус сразу.</div>{}</div>',
            obj.get_kind_display(), format_html("".join(str(button) for button in buttons)),
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
    def image_preview(self, obj):
        item = obj.items.first()
        if not item or not getattr(item, "variant", None):
            return format_html(
                '<div style="width:75px;height:75px;border-radius:8px;background:#f9f9f9;'
                'display:flex;align-items:center;justify-content:center;color:#999;font-size:12px;border:1px solid #ddd;">–</div>'
            )

        # безопасно достаём первую картинку
        images_mgr = getattr(item.variant, "images", None)
        first_img_obj = images_mgr.first() if images_mgr else None
        img_field = getattr(first_img_obj, "image", None)
        img_url = getattr(img_field, "url", None)

        if img_url:
            return format_html(
                '<div style="width:75px;height:75px;overflow:hidden;border-radius:8px;'
                'background:#f9f9f9;display:flex;align-items:center;justify-content:center;border:1px solid #ddd;">'
                '<img src="{}" style="max-width:100%;max-height:100%;object-fit:contain"/></div>',
                img_url
            )

        return format_html(
            '<div style="width:75px;height:75px;border-radius:8px;background:#f9f9f9;'
            'display:flex;align-items:center;justify-content:center;color:#999;font-size:12px;border:1px solid #ddd;">–</div>'
        )

    image_preview.short_description = "Фото"

    def identity(self, obj: Order):
        who = obj.user_name or "—"
        phone = obj.contact_phone or ""
        email = obj.email or ""

        # палитры чипов
        COLORS = {
            "user":  ("#eef2ff", "#c7d2fe", "#4338ca"),  # синий
            "who":   ("#ecfeff", "#a5f3fc", "#155e75"),  # бирюзовый
            "phone": ("#fef3c7", "#fde68a", "#92400e"),  # янтарный
            "email": ("#f0fdf4", "#bbf7d0", "#166534"),  # зелёный
        }

        def chip(text, key, href=None):
            bg, br, fg = COLORS[key]
            style = (
                f"padding:2px 8px;border-radius:999px;"
                f"background:{bg};border:1px solid {br};color:{fg};"
                f"font-size:11px;text-decoration:none;display:inline-block;"
            )
            if href:
                return format_html('<a href="{}" target="_blank" rel="noopener" style="{}">{}</a>', href, style, text)
            return format_html('<span style="{}">{}</span>', style, text)

        # чип пользователя (ссылка в админку)
        user_chip = ""
        if obj.user_id and obj.user:
            u = obj.user
            u_url = reverse(
                f"admin:{u._meta.app_label}_{u._meta.model_name}_change",
                args=[admin_quote(u.pk)]
            )
            label = getattr(u, "email", None) or getattr(u, "telegram_username", None) or f"user#{str(u.pk)}"
            user_chip = chip(label, "user", href=u_url)

        who_chip   = chip(who,   "who")
        phone_chip = chip(phone, "phone") if phone else ""

        return format_html(
            '''
            <div style="line-height:1.45;font-size:13px;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                <button type="button" data-oid="{oid}"
                        onclick="(function(el){{var t=el.getAttribute('data-oid');try{{navigator.clipboard.writeText(t);}}catch(_e){{var i=document.createElement('input');i.value=t;document.body.appendChild(i);i.select();document.execCommand('copy');i.remove();}}var n=document.createElement('div');n.textContent='Скопировано #'+t;n.style.cssText='position:fixed;left:50%;top:16px;transform:translateX(-50%);background:#111827;color:#fff;padding:6px 10px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.2);font-size:12px;z-index:99999';document.body.appendChild(n);setTimeout(function(){{n.remove();}},1200);}})(this)"
                        title="Скопировать номер"
                        style="padding:4px 8px;border:1px solid #e5e7eb;border-radius:999px;cursor:pointer;font-weight:600;">
                Заказ #{oid}
                </button>
            </div>

            <div style="display:flex;flex-direction:column;gap:6px;align-items:flex-start;">
                {user_chip}
                {who_chip}
                {phone_chip}
            </div>
            </div>
            ''',
            oid=obj.order_id,
            user_chip=user_chip,
            who_chip=who_chip,
            phone_chip=phone_chip,
        )
    identity.short_description = "Визитка"

    # Бейдж статуса
    def status_badge(self, obj: Order):
        colors = {
            "created":   ("#eef2ff", "#c7d2fe", "#4338ca"),
            "paid":      ("#ecfdf5", "#6ee7b7", "#047857"),
            "assembled": ("#fefce8", "#fde68a", "#92400e"),
            "shipped":   ("#eff6ff", "#bfdbfe", "#1d4ed8"),
            "delivered": ("#f0fdf4", "#bbf7d0", "#166534"),
            "canceled":  ("#fef2f2", "#fecaca", "#b91c1c"),
        }
        bg, br, fg = colors.get(obj.status, ("#f3f4f6", "#e5e7eb", "#374151"))
        label = dict(Order.STATUS_CHOICES).get(obj.status, obj.status)
        return format_html(
            '<span style="background:{};border:1px solid {};color:{};'
            'padding:2px 8px;border-radius:999px;font-size:11px;">{}</span>',
            bg, br, fg, label
        )
    status_badge.short_description = "Статус"


    def storefront_link(self, obj: Order):
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">Открыть',
            obj.get_absolute_url()
        )
    storefront_link.short_description = "На сайте"


# ───────────────────────────── PICKUP ───────────────────────────── #

@admin.register(PickupPoint)
class PickupPointAdmin(ColumnToggleModelAdmin):
    list_display = ("code", "title", "city", "address", "schedule", "is_active", "sort")
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
