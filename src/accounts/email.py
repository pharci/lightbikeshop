from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.utils.html import escape
from django.utils.timezone import localtime

# ===== Общие хелперы =====

def call_or_val(obj, attr, default=""):
    if not hasattr(obj, attr):
        return default
    v = getattr(obj, attr)
    try:
        return v() if callable(v) else v
    except Exception:
        return default

def to_decimal(v) -> Decimal:
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")

def money(v) -> str:
    return f"{to_decimal(v):.2f}₽"

def site_base() -> str:
    url = getattr(settings, "SITE_URL", "") or ""
    if url:
        return url.rstrip("/")
    try:
        from django.contrib.sites.models import Site
        domain = Site.objects.get_current().domain.strip()
        if not domain.startswith(("http://", "https://")):
            scheme = getattr(settings, "SITE_SCHEME", "https")
            return f"{scheme}://{domain}".rstrip("/")
        return domain.rstrip("/")
    except Exception:
        pass
    host = (getattr(settings, "ALLOWED_HOSTS", []) or [""])[0]
    return (f"https://{host}".rstrip("/")) if host else ""

BASE_URL = site_base()

def abs_url(path: str) -> str:
    if not path:
        return ""
    if path.startswith(("http://", "https://")):
        return path
    return f"{BASE_URL}{path}" if BASE_URL else path

def human_status_raw(status_value: str, pvz_provider: str) -> str:
    if pvz_provider == "Самовывоз":
        mapping = {
            "created": "Создан",
            "paid": "Оплачен",
            "assembled": "Готов к выдаче",
            "delivered": "Завершён",
            "canceled": "Отменён",
        }
    else:
        mapping = {
            "created": "Создан",
            "paid": "Оплачен",
            "assembled": "Собран",
            "shipped": "Отправлен",
            "delivered": "Доставлен",
            "canceled": "Отменён",
        }
    return mapping.get(status_value) or status_value

def human_status_current(order) -> str:
    try:
        return str(order.get_status_display())
    except Exception:
        return human_status_raw(getattr(order, "status", ""), getattr(order, "pvz_provider", ""))

def prefetch_items(order):
    try:
        return list(order.items.select_related("variant").prefetch_related("variant__images"))
    except Exception:
        return list(order.items.all())

def item_row_html(it) -> str:
    v = it.variant
    try:
        imgs = list(getattr(v, "images").all())
    except Exception:
        imgs = []
    if imgs:
        img = sorted(imgs, key=lambda x: (getattr(x, "sort", 0), getattr(x, "id", 0)))[0]
        img_url = abs_url(getattr(getattr(img, "image", None), "url", "") or "")
        img_alt = escape(getattr(img, "alt", "") or call_or_val(v, "display_name", "Фото"))
    else:
        img_url, img_alt = "", "Фото"

    name = escape(str(call_or_val(v, "display_name", "Товар")))
    href = abs_url(str(call_or_val(v, "get_absolute_url", "#")))
    qty = escape(str(it.quantity))
    price = money(it.price)
    total_line = money(to_decimal(it.price) * to_decimal(it.quantity))
    img_html = (
        f'<img src="{img_url}" alt="{img_alt}" width="56" height="56" style="border-radius:8px;display:block;object-fit:cover;" />'
        if img_url else
        '<div style="width:56px;height:56px;border-radius:8px;background:#e5e7eb;"></div>'
    )
    return f"""
      <tr>
        <td style="padding:10px 0;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;">
            <tr>
              <td style="width:64px;vertical-align:top">{img_html}</td>
              <td style="vertical-align:top;">
                <a href="{href}" style="font-size:14px;color:#111827;text-decoration:none;font-weight:600">{name}</a>
                <div style="font-size:12px;color:#6b7280;margin-top:4px;">Количество: {qty}</div>
              </td>
              <td style="vertical-align:top;text-align:right;white-space:nowrap;">
                <div style="font-size:13px;color:#111827">{price}</div>
                <div style="font-size:12px;color:#6b7280">Сумма: {total_line}</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    """

def shipping_text_lines(order) -> list[str]:
    lines = []
    pvz = getattr(order, "pvz_provider", "")
    if pvz == "Самовывоз":
        lines.append("Метод получения: Самовывоз")
    else:
        method = "ПВЗ" if getattr(order, "pvz_code", "") else "Доставка"
        provider = f" ({order.pvz_provider})" if getattr(order, "pvz_code", "") else ""
        lines.append(f"Метод получения: {method}{provider}")
        if getattr(order, "pvz_code", ""):
            lines.append(f"Код ПВЗ: {order.pvz_code}")
        if getattr(order, "pvz_address", ""):
            lines.append(f"Адрес: {order.pvz_address}")
    return lines

def shipping_html(order) -> str:
    pvz = getattr(order, "pvz_provider", "")
    parts = []
    if pvz == "Самовывоз":
        parts.append('<div style="margin:4px 0;"><span style="color:#6b7280">Метод получения</span>: Самовывоз</div>')
    else:
        method = "ПВЗ" if getattr(order, "pvz_code", "") else "Доставка"
        provider = f" ({escape(order.pvz_provider)})" if getattr(order, "pvz_code", "") else ""
        parts.append(f'<div style="margin:4px 0;"><span style="color:#6b7280">Метод получения</span>: {method}{provider}</div>')
        if getattr(order, "pvz_code", ""):
            parts.append(f'<div style="margin:4px 0;"><span style="color:#6b7280">Код ПВЗ</span>: {escape(order.pvz_code)}</div>')
        if getattr(order, "pvz_address", ""):
            parts.append(f'<div style="margin:4px 0;"><span style="color:#6b7280">Адрес</span>: {escape(order.pvz_address)}</div>')
    return "".join(parts)

def order_url(order) -> str:
    return abs_url(call_or_val(order, "get_absolute_url", "#"))

def total_count_safe(order) -> str:
    return str(call_or_val(order, "get_total_count", getattr(order, "get_total_count", "")))

def date_str_local(dt) -> str:
    return localtime(dt).strftime("%d.%m.%Y, %H:%M")



def send_verification_code(email: str, code: str) -> None:
    site_name = getattr(settings, "SITE_NAME", "LIGHTBIKESHOP")
    subject = f"{site_name} — подтверждение входа"
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [email]
    home_url = abs_url("/")

    text_message = (
        f"Код для входа в {site_name}: {code}\n"
        f"Войти: {home_url}"
    )

    html_message = f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
      <div style="background:#111827;padding:18px;text-align:center;">
        <h1 style="margin:0;font-size:22px;font-weight:800;color:#fff;letter-spacing:1px;">{escape(site_name)}</h1>
      </div>
      <div style="padding:24px;color:#111827;">
        <h2 style="margin-top:0;font-size:20px;">Подтверждение входа</h2>
        <p style="font-size:15px;margin-bottom:18px;">
          Используйте этот код, чтобы войти в аккаунт на сайте
          <strong><a style="text-decoration:none;color:#111827;" href="{home_url}">{escape(site_name)}</a></strong>:
        </p>
        <div style="font-size:32px;font-weight:bold;letter-spacing:6px;padding:20px;background:#fff;border:2px dashed #111827;border-radius:10px;text-align:center;margin:20px 0;color:#111827;">
          {escape(code)}
        </div>
        <p style="font-size:13px;color:#6b7280;margin-top:16px;">
          Код действителен несколько минут. Если вы не запрашивали вход, проигнорируйте письмо.
        </p>
      </div>
      <div style="background:#f3f4f6;padding:14px;text-align:center;font-size:12px;color:#6b7280;">
        © {escape(site_name)}
      </div>
    </div>
    """

    email_obj = EmailMultiAlternatives(subject, text_message, from_email, recipient_list)
    email_obj.attach_alternative(html_message, "text/html")
    email_obj.send()


def send_order_created_email(email: str, order) -> None:
    items = prefetch_items(order)
    site_name = getattr(settings, "SITE_NAME", "LIGHTBIKESHOP")
    subject = f"{site_name} — заказ №{order.order_id} оформлен"
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [email]

    # text
    text_lines = [
        f"Заказ №{order.order_id} — {human_status_current(order)}",
        f"Дата: {date_str_local(order.date_ordered)}",
        *shipping_text_lines(order),
        "",
        "Товары:",
    ]
    for it in items:
        name = call_or_val(it.variant, "display_name", "Товар")
        text_lines.append(f"- {name} ×{it.quantity} — {money(it.price)}")

    text_lines += [
        "",
        "Итоги:",
        f"Количество: {total_count_safe(order)}",
        f"Без скидок: {money(order.subtotal)}",
    ]
    if to_decimal(getattr(order, "discount_total", 0)) != 0:
        text_lines.append(f"Скидка: -{money(order.discount_total)}")
    if to_decimal(getattr(order, "shipping_total", 0)) != 0:
        text_lines.append(f"Доставка: {money(order.shipping_total)}")
    text_lines.append(f"Итого к оплате: {money(order.total)}")

    ou = order_url(order)
    text_lines.append(f"\nПодробнее: {ou}")
    if getattr(order, "status", "") == "created" and getattr(order, "payment_url", ""):
        text_lines.append(f"Оплатить: {abs_url(order.payment_url)}")

    text_message = "\n".join(text_lines)

    # html
    html_items = "\n".join(item_row_html(it) for it in items)
    pay_btn_html = (
        f'<a href="{abs_url(order.payment_url)}" style="display:inline-block;background:#0d6efd;color:#fff;text-decoration:none;font-weight:700;padding:12px 18px;border-radius:10px;">Оплатить</a>'
        if getattr(order, "status", "") == "created" and getattr(order, "payment_url", "") else ""
    )
    html_message = f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
      <div style="background:#111827;padding:18px;text-align:center;">
        <h1 style="margin:0;font-size:22px;font-weight:800;color:#fff;letter-spacing:1px;">{escape(site_name)}</h1>
      </div>
      <div style="padding:24px;color:#111827;background:#ffffff">
        <h2 style="margin:0 0 6px;font-size:20px;">Заказ № {escape(str(order.order_id))} — {escape(human_status_current(order))}</h2>
        <div style="font-size:14px;color:#6b7280;margin-bottom:14px;">Дата оформления: {escape(date_str_local(order.date_ordered))}</div>
        <div style="font-size:14px;margin:12px 0 18px;">{shipping_html(order)}</div>
        <div style="font-weight:700;margin:12px 0 8px;">Товары</div>
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;">
          {html_items}
        </table>
        <div style="margin-top:18px;padding-top:12px;border-top:1px solid #e5e7eb;">
          <div style="display:flex;justify-content:space-between;font-size:14px;margin:6px 0;"><span style="color:#6b7280">Количество товаров </span><span>{escape(total_count_safe(order))}</span></div>
          <div style="display:flex;justify-content:space-between;font-size:14px;margin:6px 0;"><span style="color:#6b7280">Без скидок </span><span>{money(order.subtotal)}</span></div>
          {f'<div style="display:flex;justify-content:space-between;font-size:14px;margin:6px 0;"><span style="color:#6b7280">Скидка </span><span>-{money(order.discount_total)}</span></div>' if to_decimal(getattr(order, 'discount_total', 0)) != 0 else ''}
          {f'<div style="display:flex;justify-content:space-between;font-size:14px;margin:6px 0;"><span style="color:#6b7280">Доставка </span><span>{money(order.shipping_total)}</span></div>' if to_decimal(getattr(order, 'shipping_total', 0)) != 0 else ''}
          <div style="display:flex;justify-content:space-between;font-size:16px;font-weight:800;margin:10px 0;"><span>Итого к оплате </span><span>{money(order.total)}</span></div>
        </div>
        <div style="margin-top:18px;display:flex;gap:10px;flex-wrap:wrap;">
          <a href="{escape(ou)}" style="display:inline-block;background:#111827;color:#fff;text-decoration:none;font-weight:700;padding:12px 18px;border-radius:10px;">Подробнее</a>
          <a href="https://t.me/light_bikeshop" style="display:inline-block;background:#6b7280;color:#fff;text-decoration:none;font-weight:700;padding:12px 18px;border-radius:10px;">Помощь</a>
          {pay_btn_html}
        </div>
        <p style="font-size:12px;color:#6b7280;margin-top:16px;">Если кнопки не работают, откройте страницу заказа: {escape(ou)}</p>
      </div>
      <div style="background:#f3f4f6;padding:14px;text-align:center;font-size:12px;color:#6b7280;">© {escape(site_name)}</div>
    </div>
    """

    email_obj = EmailMultiAlternatives(subject, text_message, from_email, recipient_list)
    email_obj.attach_alternative(html_message, "text/html")
    email_obj.send()



def send_order_status_changed_email(email: str, order) -> None:
    items = prefetch_items(order)
    site_name = getattr(settings, "SITE_NAME", "LIGHTBIKESHOP")
    new_h = human_status_current(order)

    subject = f"{site_name} — заказ №{order.order_id}, статус: {new_h}"
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [email]

    # text
    text_lines = [
        f"Заказ №{order.order_id}: {new_h}",
        f"Дата оформления: {date_str_local(order.date_ordered)}",
        *shipping_text_lines(order),
        "",
        "Товары:",
    ]
    for it in items:
        name = call_or_val(it.variant, "display_name", "Товар")
        text_lines.append(f"- {name} ×{it.quantity} — {money(it.price)}")

    text_lines += [
        "",
        "Итоги:",
        f"Количество: {total_count_safe(order)}",
        f"Без скидок: {money(order.subtotal)}",
    ]
    if to_decimal(getattr(order, "discount_total", 0)) != 0:
        text_lines.append(f"Скидка: -{money(order.discount_total)}")
    if to_decimal(getattr(order, "shipping_total", 0)) != 0:
        text_lines.append(f"Доставка: {money(order.shipping_total)}")
    text_lines.append(f"Итого: {money(order.total)}")

    ou = order_url(order)
    text_lines.append(f"\nПодробнее: {ou}")
    text_message = "\n".join(text_lines)

    # html
    html_items = "\n".join(item_row_html(it) for it in items)
    html_message = f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
      <div style="background:#111827;padding:18px;text-align:center;">
        <h1 style="margin:0;font-size:22px;font-weight:800;color:#fff;letter-spacing:1px;">{escape(site_name)}</h1>
      </div>
      <div style="padding:24px;color:#111827;background:#ffffff">
        <h2 style="margin:0 0 6px;font-size:20px;">Заказ № {escape(str(order.order_id))} — {escape(new_h)}</h2>
        <div style="font-size:14px;color:#6b7280;margin-bottom:14px;">Дата оформления: {escape(date_str_local(order.date_ordered))}</div>

        <div style="font-size:14px;margin:12px 0 6px;">{shipping_html(order)}</div>

        <div style="font-weight:700;margin:12px 0 8px;">Товары</div>
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;">
          {html_items}
        </table>

        <div style="margin-top:18px;padding-top:12px;border-top:1px solid #e5e7eb;">
          <div style="display:flex;justify-content:space-between;font-size:14px;margin:6px 0;"><span style="color:#6b7280">Количество товаров </span><span>{escape(total_count_safe(order))}</span></div>
          <div style="display:flex;justify-content:space-between;font-size:14px;margin:6px 0;"><span style="color:#6b7280">Без скидок </span><span>{money(order.subtotal)}</span></div>
          {f'<div style="display:flex;justify-content:space-between;font-size:14px;margin:6px 0;"><span style="color:#6b7280">Скидка </span><span>-{money(order.discount_total)}</span></div>' if to_decimal(getattr(order, 'discount_total', 0)) != 0 else ''}
          {f'<div style="display:flex;justify-content:space-between;font-size:14px;margin:6px 0;"><span style="color:#6b7280">Доставка </span><span>{money(order.shipping_total)}</span></div>' if to_decimal(getattr(order, 'shipping_total', 0)) != 0 else ''}
          <div style="display:flex;justify-content:space-between;font-size:16px;font-weight:800;margin:10px 0;"><span>Итого </span><span>{money(order.total)}</span></div>
        </div>

        <div style="margin-top:18px;display:flex;gap:10px;flex-wrap:wrap;">
          <a href="{escape(ou)}" style="display:inline-block;background:#111827;color:#fff;text-decoration:none;font-weight:700;padding:12px 18px;border-radius:10px;">Подробнее</a>
          <a href="https://t.me/light_bikeshop" style="display:inline-block;background:#6b7280;color:#fff;text-decoration:none;font-weight:700;padding:12px 18px;border-radius:10px;">Помощь</a>
        </div>

        <p style="font-size:12px;color:#6b7280;margin-top:16px;">Если кнопки не работают, откройте страницу заказа: {escape(ou)}</p>
      </div>

      <div style="background:#f3f4f6;padding:14px;text-align:center;font-size:12px;color:#6b7280;">© {escape(site_name)}</div>
    </div>
    """

    email_obj = EmailMultiAlternatives(subject, text_message, from_email, recipient_list)
    email_obj.attach_alternative(html_message, "text/html")
    email_obj.send()