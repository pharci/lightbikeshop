from django.contrib import admin
from .models import User
from column_toggle.admin import ColumnToggleModelAdmin
from django.utils.html import format_html

@admin.register(User)
class UserAdmin(ColumnToggleModelAdmin):
    """
    Красивая админка пользователей: компактная «визитка» + переключаемые колонки.
    """
    list_display = (
        "identity", "email", "telegram_username", "telegram_id",
        "is_active", "is_staff", "is_superuser", "last_login",
    )
    default_selected_columns = ["identity", "email", "telegram_username", "is_active", "last_login"]
    list_display_links = ("identity",)
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("email", "telegram_username", "telegram_id")
    ordering = ("-id",)
    readonly_fields = ("last_login",)

    fieldsets = (
        (None, {
            "fields": ("email", "telegram_username", "telegram_id", "password")
        }),
        ("Статус и доступ", {
            "fields": ("is_active", "is_staff", "is_superuser", "last_login")
        }),
    )

    def identity(self, obj: User):
        """
        Мини-«визитка»: показывает email или @username c маленьким бейджем.
        """
        # Основная подпись
        if obj.email:
            primary = obj.email
            badge = '<span style="background:#eef5ff;border:1px solid #cfe2ff;color:#1b6ef3;padding:1px 6px;border-radius:6px;font-size:11px;margin-left:6px;">email</span>'
        elif obj.telegram_username:
            primary = f"@{obj.telegram_username}"
            badge = '<span style="background:#e9f7ff;border:1px solid #bfe9ff;color:#0a91cf;padding:1px 6px;border-radius:6px;font-size:11px;margin-left:6px;">telegram</span>'
        elif obj.telegram_id:
            primary = f"tg_id:{obj.telegram_id}"
            badge = '<span style="background:#e9f7ff;border:1px solid #bfe9ff;color:#0a91cf;padding:1px 6px;border-radius:6px;font-size:11px;margin-left:6px;">telegram</span>'
        else:
            primary = f"user#{obj.id}"
            badge = ""

        # Буллет статусов
        dot_color = "#22c55e" if obj.is_active else "#ef4444"
        dot = f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{dot_color};margin-right:6px;vertical-align:middle;"></span>'

        return format_html(
            '<div style="display:flex;align-items:center;gap:8px;">'
            '  <div style="width:28px;height:28px;border-radius:6px;background:#f3f4f6;display:flex;align-items:center;justify-content:center;border:1px solid #e5e7eb;font-size:12px;color:#6b7280;">{initial}</div>'
            '  <div style="line-height:1.2;">{dot}<strong>{primary}</strong> {badge}</div>'
            '</div>',
            initial=(primary[:2].upper().replace("@", "")),
            dot=format_html(dot),
            primary=primary,
            badge=format_html(badge),
        )
    identity.short_description = "Пользователь"