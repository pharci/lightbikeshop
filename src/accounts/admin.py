from django.contrib import admin, messages
from .models import User
from column_toggle.admin import ColumnToggleModelAdmin
from django.utils.html import format_html
from django import forms
from .tasks import start_broadcast
from django.shortcuts import render, redirect
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME

class BroadcastForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput, required=False)
    text = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 6, "style": "width:100%"}),
        label="Сообщение",
        help_text="Можно использовать HTML-разметку",
    )

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
    actions = ["send_tg_broadcast"]

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

    def send_tg_broadcast(self, request, queryset):
        if "apply" in request.POST:
            form = BroadcastForm(request.POST)
            if form.is_valid():
                chat_ids = list(
                    queryset.exclude(telegram_id__isnull=True)
                            .exclude(telegram_id="")
                            .values_list("telegram_id", flat=True)
                )
                start_broadcast(chat_ids, form.cleaned_data["text"])
                self.message_user(
                    request,
                    f"Запущена рассылка: {len(chat_ids)} получателей",
                    messages.SUCCESS,
                )
                return redirect(request.get_full_path())
        else:
            form = BroadcastForm(
                initial={"_selected_action": request.POST.getlist(ACTION_CHECKBOX_NAME)}
            )

        return render(
            request,
            "admin/broadcast.html",
            {
                "form": form,
                "title": "Telegram-рассылка",
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
                "queryset": queryset,
            },
        )

    send_tg_broadcast.short_description = "Отправить рассылку в Telegram"