# core/telegram.py
import requests
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from django.utils.html import escape

TG_API = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"

RECIPIENTS = [787640915, 483918282, 5627367620]  # я, Андрей, менеджер

def _send_tg(chat_id: int, text: str, reply_markup: dict | None = None):
    def chunks(s, n=4096):
        for i in range(0, len(s), n):
            yield s[i:i+n]

    last_resp = None
    for part in chunks(text):
        payload = {
            "chat_id": chat_id,
            "text": part,
            "parse_mode": "HTML",           # попробуем HTML
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        # 1) JSON
        try:
            resp = requests.post(f"{TG_API}/sendMessage", json=payload, timeout=20)
            last_resp = resp
            if resp.status_code != 200:
                print("TG POST JSON status:", resp.status_code, resp.text)
                resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                print("TG JSON error:", data)
                # 2) Фолбэк: form-encoded без parse_mode
                payload.pop("parse_mode", None)
                resp = requests.post(f"{TG_API}/sendMessage", data=payload, timeout=20)
                last_resp = resp
                if resp.status_code != 200:
                    print("TG POST FORM status:", resp.status_code, resp.text)
                    resp.raise_for_status()
                data = resp.json()
                if not data.get("ok"):
                    raise RuntimeError(f"Telegram error: {data}")
        except Exception as e:
            print("Telegram send error:", repr(e))
            raise
    return last_resp

def send_tg_order(order, request):
    domain = get_current_site(request).domain
    admin_url = f"http://{domain}{reverse('admin:cart_order_change', args=[order.id])}"

    # ------- текст -------
    esc = escape
    lines = [
        f"<b>Заказ <a href='{admin_url}'>№{esc(order.order_id)}</a></b>",
        "",
        f"<b>Статус:</b> {esc(order.get_status_display())}",
        f"<b>Имя:</b> <code>{esc(order.user_name)}</code>",
        f"<b>Телефон:</b> {esc(order.contact_phone)}",
    ]
    if order.email:
        lines.append(f"<b>Email:</b> {esc(order.email)}")
    if order.order_notes:
        lines.append(f"<b>Комментарий:</b> {esc(order.order_notes)}")
    lines.append("")

    lines.append("<b>Товары:</b>")
    lines.append("<blockquote>Кол-во × Название: Цена")
    for it in order.items.select_related("variant"):
        url = f"{request.build_absolute_uri(it.variant.get_absolute_url())}"
        lines.append(
            f"{it.quantity} × <a href='{url}'>{it.variant.display_name()}:</a> {it.price} ₽"
        )

    lines.append("</blockquote>")
    lines.append(f"<b>Итого товаров:</b> {order.get_total_count()} шт")
    lines.append(f"<b>Сумма:</b> {order.get_total_price()} ₽")

    text = "\n".join(lines)

    # ------- клавиатура -------
    kb = {
        "inline_keyboard": [
            [
                {"text": "Открыть в админке", "url": admin_url},
            ],
            [
                {"text": "Написать в TG", "url": f"https://t.me/{order.contact_phone}"},
            ],
            [
                {"text": "✅ В обработке", "callback_data": f"ord:{order.owner_token}:processing"},
                {"text": "📦 Готов к выдаче", "callback_data": f"ord:{order.owner_token}:ready_for_shipping"},
            ],
            [
                {"text": "🚚 Отправлен", "callback_data": f"ord:{order.owner_token}:shipped"},
                {"text": "✔️ Завершен", "callback_data": f"ord:{order.owner_token}:completed"},
            ],
            [
                {"text": "🛑 Отменен", "callback_data": f"ord:{order.owner_token}:canceled"},
            ],
        ]
    }

    # ------- рассылка -------
    for cid in RECIPIENTS:
        _send_tg(cid, text, kb)

    return text
