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
    esc = escape
    fmt = lambda x: f"{x:,.2f}".replace(",", " ")

    scheme = "https" if request.is_secure() else "http"
    domain = get_current_site(request).domain
    admin_url = f"{scheme}://{domain}{reverse('admin:cart_order_change', args=[order.id])}"

    ms_url = None
    if getattr(order, "ms_order_id", None):
        ms_id = str(order.ms_order_id)
        base = getattr(settings, "MOYSKLAD_URL", "https://online.moysklad.ru/app")
        ms_url = f"{base}/#customerorder/edit?id={ms_id}"

    lines = [f"<b>Заказ <a href='{admin_url}'>№{esc(order.order_id)}</a></b>"]
    if ms_url:
        lines.append(f"Ссылка на <b><a href='{ms_url}'>МойСклад</a></b>")

    lines += [
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
    if order.pvz_code:
        lines.append(f"<b>ПВЗ: {esc(order.pvz_code)}</b>")
    else:
        lines.append("<b>Самовывоз</b>")
    if order.pvz_address:
        lines.append(f"<blockquote>{esc(order.city.strip())} {esc(order.pvz_address.strip())}</blockquote>")

    lines.append("")
    lines.append("<b>Товары:</b>")
    lines.append("<blockquote>Кол-во × Название: Цена")

    for it in order.items.select_related("variant"):
        url = request.build_absolute_uri(it.variant.get_absolute_url())
        lines.append(f"{it.quantity} × <a href='{url}'>{esc(it.variant.display_name())}</a>: {fmt(it.price)} ₽")
    lines.append("</blockquote>")

    if order.promo_code:
        lines += [
            f"<b>Промокод:</b> {esc(order.promo_code.code)}", 
            "",
        ]

    # блок сумм из новых полей
    lines += [

        f"<b>Итого товаров:</b> {order.get_total_count()} шт",
        f"<b>Сумма без скидок:</b> {fmt(order.subtotal)} ₽",
        f"<b>Скидка всего:</b> -{fmt(order.discount_total)} ₽",
        f"<b>Доставка:</b> {fmt(order.shipping_total)} ₽",
        f"",
        f"<b>Итого к оплате:</b> {fmt(order.total)} ₽"
    ]

    text = "\n".join(lines)

    phone_digits = "".join(ch for ch in (order.contact_phone or "") if ch.isdigit() or ch == "+")
    tg_link = f"tg://resolve?phone={phone_digits}" if phone_digits else admin_url

    kb_rows = [
        [{"text": "Написать в TG", "url": tg_link}],
        *([[{"text": "Открыть в МойСклад", "url": ms_url}]] if ms_url else []),
        [{"text": "Открыть в админке", "url": admin_url}],
    ]
    kb = {"inline_keyboard": kb_rows}

    for cid in RECIPIENTS:
        _send_tg(cid, text, kb)  # внутри parse_mode='HTML'

    return text
