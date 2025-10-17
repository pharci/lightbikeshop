# accounts/admin.py
from __future__ import annotations
from datetime import timedelta

from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from django import forms

from column_toggle.admin import ColumnToggleModelAdmin

from .models import User, EmailOTP
from .tasks import start_broadcast
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME


# ===================== User =====================

class BroadcastForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput, required=False)
    text = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 6, "style": "width:100%"}),
        label="Сообщение",
        help_text="Можно использовать HTML-разметку",
    )

@admin.register(User)
class UserAdmin(ColumnToggleModelAdmin):
    list_display = (
        "identity", "email", "telegram_username", "telegram_id",
        "is_active", "is_staff", "is_superuser", "last_login",
    )
    default_selected_columns = ["identity", "email", "telegram_username", "is_active", "last_login"]
    list_display_links = ("identity",)
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("email", "telegram_username", "telegram_id")
    ordering = ("-id",)
    readonly_fields = ("last_login", "date_joined")
    actions = ["send_tg_broadcast"]

    fieldsets = (
        (None, {"fields": ("email", "first_name", "last_name")}),
        ("Telegram", {"fields": ("telegram_username", "telegram_id")}),
        ("Статус и доступ", {"fields": ("is_active", "is_staff", "is_superuser", "last_login", "date_joined")}),
        ("Права", {"fields": ("groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "first_name", "last_name", "is_active", "is_staff", "is_superuser")}),
    )

    def identity(self, obj: User):
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
                self.message_user(request, f"Запущена рассылка: {len(chat_ids)} получателей", messages.SUCCESS)
                return None
        else:
            form = BroadcastForm(initial={"_selected_action": request.POST.getlist(ACTION_CHECKBOX_NAME)})
        from django.shortcuts import render
        return render(
            request,
            "admin/broadcast.html",
            {"form": form, "title": "Telegram-рассылка", "action_checkbox_name": ACTION_CHECKBOX_NAME, "queryset": queryset},
        )
    send_tg_broadcast.short_description = "Отправить рассылку в Telegram"


# ===================== EmailOTP =====================

@admin.register(EmailOTP)
class EmailOTPAdmin(ColumnToggleModelAdmin):
    list_display = (
        "short_id", "email", "status_badge", "attempts_progress",
        "secret_id", "expires_at", "created_at", "ip", "ua",
    )
    default_selected_columns = ["short_id", "email", "status_badge", "attempts_progress", "expires_at", "created_at"]
    list_display_links = ("short_id", "email")
    search_fields = ("email", "request_id", "secret_id", "ip", "ua")
    list_filter = ("secret_id", "max_attempts", ("expires_at", admin.DateFieldListFilter), ("created_at", admin.DateFieldListFilter))
    ordering = ("-created_at",)
    readonly_fields = (
        "request_id", "email", "code_hmac", "secret_id", "expires_at",
        "consumed_at", "attempts", "max_attempts", "ip", "ua", "created_at",
        "status_badge", "attempts_progress",
    )
    fieldsets = (
        (None, {"fields": ("request_id", "email", "secret_id", "code_hmac")}),
        ("Состояние", {"fields": ("status_badge", "attempts_progress", "attempts", "max_attempts", "expires_at", "consumed_at")}),
        ("Мета", {"fields": ("ip", "ua", "created_at")}),
    )
    actions = ["mark_consumed", "purge_expired"]

    # представление

    def short_id(self, obj: EmailOTP):
        return str(obj.request_id)[:8]
    short_id.short_description = "ID"

    def status_badge(self, obj: EmailOTP):
        now = timezone.now()
        if obj.consumed_at:
            color, text = ("#22c55e", "использован")
        elif now > obj.expires_at:
            color, text = ("#ef4444", "истёк")
        elif obj.attempts >= obj.max_attempts:
            color, text = ("#f59e0b", "лимит")
        else:
            color, text = ("#3b82f6", "активен")
        return format_html(
            '<span style="display:inline-block;padding:2px 8px;border-radius:999px;background:{bg};color:#111;border:1px solid rgba(0,0,0,.06);font-size:12px;">{text}</span>',
            bg=color, text=text
        )
    status_badge.short_description = "Статус"

    def attempts_progress(self, obj: EmailOTP):
        return f"{obj.attempts}/{obj.max_attempts}"
    attempts_progress.short_description = "Попытки"

    # действия

    def mark_consumed(self, request, queryset):
        n = queryset.update(consumed_at=timezone.now())
        self.message_user(request, f"Помечено использованными: {n}", level=messages.SUCCESS)
    mark_consumed.short_description = "Пометить использованными"

    def purge_expired(self, request, queryset):
        now = timezone.now()
        qs = queryset.filter(expires_at__lt=now)
        n = qs.count()
        qs.delete()
        self.message_user(request, f"Удалено истёкших: {n}", level=messages.SUCCESS)
    purge_expired.short_description = "Удалить истёкшие"
