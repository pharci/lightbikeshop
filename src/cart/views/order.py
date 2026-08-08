import json
import logging
import requests
from django.conf import settings
from django.contrib import messages
from django.db import IntegrityError, connection, transaction
from django.http import HttpRequest, JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache

from accounts.telegram import send_tg_order, send_tg_order_status
from cart.signals_copurchase_variant import bump_copurchases_variants
from cart.order_utils import iter_cart_variants, D
from cart.MS import create_customer_order, set_ms_order_state_by_uuid, _get
from cart.forms import CheckoutForm
from cart.models import Order, OrderItem, PaymentAttempt

from .tpay import check_order, create_PaymentURL
from .cart import get_cart
from .cdek import calc_cdek_pvz_price
from accounts.email import send_order_created_email, send_order_status_changed_email

logger = logging.getLogger(__name__)
PENDING_ORDER_SESSION_KEY = "pending_checkout_order"


def _cart_matches_order(lines, order):
    return sorted((str(v.pk), int(q)) for v, q in lines) == sorted(
        (str(item.variant_id), int(item.quantity)) for item in order.items.all()
    )


def _pending_order(request, lines):
    pk = request.session.get(PENDING_ORDER_SESSION_KEY)
    if not pk:
        return None
    order = Order.objects.filter(pk=pk, status__in=("created", "auth")).first()
    if not order or not _cart_matches_order(lines, order):
        return None
    if request.user.is_authenticated:
        return order if order.user_id == request.user.id else None
    return order if order.user_id is None else None


def _attempt_bank_order_id(order):
    count = order.payment_attempts.count()
    return order.order_id if count == 0 else f"{order.order_id}-{count + 1}"


def _acquire_order_advisory_lock(order_pk):
    if connection.vendor != "postgresql":
        return False
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s)", [order_pk])
    return True


def _release_order_advisory_lock(order_pk):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_unlock(%s)", [order_pk])


def _recover_attempt(attempt):
    data = check_order(attempt.bank_order_id)
    if not data:
        return None

    payment_id = data.get("PaymentId")
    payment_url = data.get("PaymentURL")
    status = str(data.get("Status") or "").upper()

    if payment_id and payment_url:
        attempt.payment_id = str(payment_id)
        attempt.payment_url = payment_url
        attempt.state = "active"
        attempt.save(update_fields=["payment_id", "payment_url", "state", "updated"])
        return "recovered"

    if status in ("AUTHORIZED", "CONFIRMED"):
        attempt.payment_id = str(payment_id) if payment_id else attempt.payment_id
        attempt.state = "auth" if status == "AUTHORIZED" else "paid"
        attempt.save(update_fields=["payment_id", "state", "updated"])
        return "finalized"

    if status in ("REJECTED", "CANCELED", "EXPIRED"):
        attempt.state = "expired" if status == "EXPIRED" else status.lower()
        attempt.save(update_fields=["state", "updated"])
        return "terminal"

    return None


def _get_payment_url(order, request):
    """Never repeat an Init whose outcome has not been reconciled."""
    lock_acquired = False
    try:
        lock_acquired = _acquire_order_advisory_lock(order.pk)

        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order.pk)
            attempt = order.payment_attempts.select_for_update().first()

            if attempt and attempt.state in ("active", "auth"):
                if attempt.payment_url:
                    return attempt.payment_url
                raise RuntimeError("Active payment has no recoverable payment URL")

            if attempt and attempt.state in ("init_pending", "init_unknown"):
                recovery_candidate = attempt
            else:
                recovery_candidate = None

            if not recovery_candidate:
                attempt = PaymentAttempt.objects.create(order=order, bank_order_id=_attempt_bank_order_id(order))
                is_new_attempt = True
            else:
                attempt = recovery_candidate
                is_new_attempt = False

            if not is_new_attempt and attempt.state in ("init_pending", "init_unknown"):
                recovery_status = _recover_attempt(attempt)
                if recovery_status == "recovered":
                    return attempt.payment_url
                if recovery_status == "finalized":
                    if attempt.payment_url:
                        return attempt.payment_url
                    raise RuntimeError("Payment is already finalized and cannot be reinitialized")
                if recovery_status == "terminal":
                    attempt = PaymentAttempt.objects.create(order=order, bank_order_id=_attempt_bank_order_id(order))
                    is_new_attempt = True
                else:
                    attempt.state = "init_unknown"
                    attempt.save(update_fields=["state", "updated"])
                    raise RuntimeError("Payment Init outcome is still unknown")

        try:
            url, payment_id = create_PaymentURL(order, request, attempt.bank_order_id)
        except Exception:
            with transaction.atomic():
                if attempt.pk:
                    PaymentAttempt.objects.filter(pk=attempt.pk, state="init_pending").update(state="init_unknown")
            raise

        with transaction.atomic():
            attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt.pk)
            if attempt.state not in ("init_pending", "init_unknown"):
                if attempt.payment_url:
                    return attempt.payment_url
                raise RuntimeError("Attempt state changed unexpectedly")

            attempt.payment_url = url
            attempt.payment_id = payment_id
            attempt.state = "active"
            attempt.save(update_fields=["payment_url", "payment_id", "state", "updated"])
            Order.objects.filter(pk=order.pk).update(payment_url=url, payment_id=payment_id)

        return url
    finally:
        if lock_acquired:
            _release_order_advisory_lock(order.pk)


@require_GET
def whereami(request: HttpRequest) -> JsonResponse:
    """Геолокация → ближайший город через DaData."""
    lat = request.GET.get("lat")
    lon = request.GET.get("lon")
    if not (lat and lon):
        return JsonResponse({"city": ""})

    try:
        resp = requests.post(
            "https://suggestions.dadata.ru/suggestions/api/4_1/rs/geolocate/address",
            headers={"Authorization": f"Token {settings.DADATA_TOKEN}"},
            json={"lat": float(lat), "lon": float(lon), "count": 1},
            timeout=5,
        )
        city = ""
        if resp.ok:
            data = resp.json()
            s0 = (data.get("suggestions") or [{}])[0]
            d = s0.get("data", {})
            city = d.get("city") or d.get("settlement") or ""
        return JsonResponse({"city": city})
    except Exception:
        return JsonResponse({"city": ""})

def order_detail(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)

    if request.user.is_authenticated and order.user_id == request.user.id:
        pass
    else:
        k = request.GET.get("k", "")
        if not k or k != order.access_key:
            return HttpResponseForbidden("forbidden")

    return render(request, "cart/order_detail.html", {"order": order})


@require_POST
def delete_order(request: HttpRequest) -> JsonResponse:
    """Отмена заказа менеджером/клиентом по номеру заказа."""
    order_id = request.POST.get("order_id")
    if not order_id:
        return JsonResponse({"message": "Заказ не найден."}, status=404)

    order = get_object_or_404(Order, order_id=order_id)

    if not request.user.is_authenticated:
        return JsonResponse({"message": "Требуется авторизация."}, status=403)

    is_owner = order.user_id == request.user.id
    is_staff = request.user.is_staff
    if not is_owner and not is_staff:
        return JsonResponse({"message": "У вас нет прав на отмену этого заказа."}, status=403)

    if order.status == "paid":
        return JsonResponse({"message": "Оплаченный заказ нельзя отменить через этот endpoint."}, status=400)

    if order.status == "canceled":
        return JsonResponse({"message": "Заказ уже отменён."})

    order.status = "canceled"
    order.save(update_fields=["status"])

    if order.ms_order_id:
        try:
            set_ms_order_state_by_uuid(order.ms_order_id, '3f5977ad-d4a4-11ee-0a80-0cba004aacf5')
        except Exception:
            logger.exception("Failed to cancel MySklad order %s", order.ms_order_id)

    return JsonResponse({"message": "Заказ успешно отменён."})


def order_status(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    return JsonResponse({"status": order.status})

@never_cache
def checkout(request):
    cart = get_cart(request)

    if request.method != "POST":
        return render(request, "cart/checkout.html", {"form": CheckoutForm(), "cart": cart})

    form = CheckoutForm(request.POST)

    if not cart or (cart.get_total_items() or 0) == 0:
        messages.error(request, "Корзина пуста.", extra_tags="global")
        return render(request, "cart/checkout.html", {"form": form, "cart": cart})

    if cart.get_cart_total_price() <= 1:
        messages.error(request, "Сумма заказа должна быть больше 1 рубля.", extra_tags="global")
        return render(request, "cart/checkout.html", {"form": form, "cart": cart})

    if not form.is_valid():
        for e in form.non_field_errors():
            messages.error(request, e, extra_tags="global")
        return render(request, "cart/checkout.html", {"form": form, "cart": cart})

    subtotal = D(cart.get_cart_subtotal_price() or 0)
    total_from_cart = D(cart.get_cart_total_price() or 0)
    discount = max(D("0.00"), subtotal - total_from_cart)

    delivery_group = form.cleaned_data.get("delivery_group") or ""
    delivery_method = form.cleaned_data.get("delivery_method") or ""
    pvz_provider = form.cleaned_data.get("pvz_provider") or ""
    pvz_code = form.cleaned_data.get("pvz_code") or ""
    pvz_address = form.cleaned_data.get("pvz_address") or ""
    city = form.cleaned_data.get("city") or ""
    city_code = form.cleaned_data.get("city_code") or None

    shipping_total = D("0.00")
    if delivery_group == "pvz" and pvz_provider == "cdek":
        shipping_total, meta = calc_cdek_pvz_price(cart, pvz_code, city_code)
        if meta.get("error"):
            logger.warning("CDEK price calculation failed for pvz_code=%s city_code=%s error=%s", pvz_code, city_code, meta.get("error"))
            messages.error(
                request,
                "Не удалось рассчитать стоимость доставки. Попробуйте ещё раз.",
                extra_tags="global",
            )
            return render(request, "cart/checkout.html", {"form": form, "cart": cart})

    lines = list(iter_cart_variants(cart))
    if not lines:
        return redirect("cart:cart")

    email = request.user.email if request.user.is_authenticated else None

    order = _pending_order(request, lines)
    if not order:
      try:
        with transaction.atomic():
            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                user_name=form.user_name,
                contact_phone=form.cleaned_data.get("contact_phone", ""),
                email=email,
                order_notes=form.cleaned_data.get("order_notes") or "",
                subtotal=subtotal.quantize(D("0.01")),
                discount_total=discount.quantize(D("0.01")),
                shipping_total=shipping_total.quantize(D("0.01")),
                total=(subtotal - discount + shipping_total).quantize(D("0.01")),
                payment_type="online",
                status="created",
                delivery_method=delivery_method,
                pvz_provider=pvz_provider,
                pvz_code=pvz_code,
                pvz_address=pvz_address,
                city=city,
                promo_code=cart.get_promo_obj(),
            )
            for v, q in lines:
                OrderItem.objects.create(order=order, variant=v, price=v.price, quantity=q, amount=(D(v.price) * int(q)).quantize(D("0.01")))
            bump_copurchases_variants([v.id for v, q in lines for _ in range(q)])
      except Exception:
        logger.exception("Failed to create order or order items for checkout")
        messages.error(request, "Не удалось оформить заказ. Попробуйте ещё раз.", extra_tags="global")
        return render(request, "cart/checkout.html", {"form": form, "cart": cart})
      request.session[PENDING_ORDER_SESSION_KEY] = order.pk
      request.session.modified = True

    if not order.ms_order_id:
      try:
        ms_data = create_customer_order(order)
        if not ms_data or not ms_data.get("id"):
            raise RuntimeError("MySklad order creation returned no id")
        order.ms_order_id = ms_data["id"]
        order.save(update_fields=["ms_order_id"])
      except Exception:
        logger.exception("MySklad order creation failed for order %s", order.order_id)
        messages.error(request, "Не удалось сохранить заказ в учёте. Попробуйте ещё раз.", extra_tags="global")
        return render(request, "cart/checkout.html", {"form": form, "cart": cart})

    try:
        url = _get_payment_url(order, request)
    except Exception:
        logger.exception("Payment URL creation failed for order %s", order.order_id)
        messages.error(request, "Не удалось сформировать ссылку на оплату. Попробуйте ещё раз.", extra_tags="global")
        return render(request, "cart/checkout.html", {"form": form, "cart": cart})

    try:
        send_tg_order(order, request)
    except Exception:
        logger.exception("Telegram notification failed for order %s", order.order_id)

    try:
        send_order_created_email(email, order)
    except Exception:
        logger.exception("Order created email failed for order %s", order.order_id)

    cart.clear()
    request.session.pop(PENDING_ORDER_SESSION_KEY, None)
    if hasattr(cart, "PROMO_KEY") and hasattr(cart, "session"):
        cart.session.pop(cart.PROMO_KEY, None)
        cart.session.modified = True

    return redirect(url)

MS_STATUS_MAP = {
    "3f597230-d4a4-11ee-0a80-0cba004aacef": "created",        # Новый
    "3f597379-d4a4-11ee-0a80-0cba004aacf0": "confirmed",      # Подтвержден
    "3f5973f2-d4a4-11ee-0a80-0cba004aacf1": "assembled",      # Собран
    "e150a7d1-a7f4-11ef-0a80-151c00235a78": "pickup",         # Самовывоз
    "3f597466-d4a4-11ee-0a80-0cba004aacf2": "shipped",        # Отгружен
    "3f5974d9-d4a4-11ee-0a80-0cba004aacf3": "delivered",      # Доставлен
    "3f59753a-d4a4-11ee-0a80-0cba004aacf4": "returned",       # Возврат
    "3f5977ad-d4a4-11ee-0a80-0cba004aacf5": "canceled",       # Отменен
    "db5148c9-9f5a-11ef-0a80-176f007f7c56": "auth",           # Платеж авторизован
    "db567a2a-9f5a-11ef-0a80-176f007f7c59": "paid",           # Оплачен
    "db582415-9f5a-11ef-0a80-176f007f7c5b": "declined",       # Отклонен
    "db5a8b19-9f5a-11ef-0a80-176f007f7c5e": "partial_return", # Частичный возврат
}

# Webhooks may arrive late or be replayed.  A MySklad event can advance an
# order, but cannot roll a payment or fulfilment status backwards.
MS_STATUS_RANK = {
    "created": 0,
    "auth": 1,
    "paid": 2,
    "confirmed": 3,
    "assembled": 4,
    "pickup": 5,
    "shipped": 6,
    "delivered": 7,
    "returned": 8,
}

@csrf_exempt
def ms_order_webhook(request):
    try:
        events = (json.loads(request.body.decode("utf-8") or "{}").get("events")) or []
    except Exception:
        return JsonResponse({"ok": True}, status=200)

    for ev in events:
        href = (ev or {}).get("meta", {}).get("href")
        if not href:
            continue
        try:
            d = _get(href)
        except Exception:
            continue
        if (d.get("meta") or {}).get("type") != "customerorder":
            continue

        ms_id = d.get("id")
        if not ms_id:
            continue

        state_href = ((d.get("state") or {}).get("meta") or {}).get("href") or ""
        state_id = state_href.rsplit("/", 1)[-1] if state_href else None
        new_status = MS_STATUS_MAP.get(state_id)

        invoice = None
        for a in d.get("attributes") or []:
            if a.get("id") == "4e9549ae-66ac-11ef-0a80-05be0019d751" or a.get("name") == "Накладная СДЭК":
                invoice = a.get("value")
                break

        changed_order_id = None
        if new_status:
            with transaction.atomic():
                order = Order.objects.select_for_update().filter(ms_order_id=ms_id).first()
                if (
                    order
                    and MS_STATUS_RANK.get(new_status, -1) > MS_STATUS_RANK.get(order.status, -1)
                ):
                    order.status = new_status
                    order.save(update_fields=["status"])
                    changed_order_id = order.pk

        if changed_order_id:
            # Notifications are intentionally outside the DB transaction: a
            # failure leaves the committed status intact and a replay does not
            # send a duplicate notification.
            try:
                order = Order.objects.get(pk=changed_order_id)
                send_tg_order_status(order, request)
                send_order_status_changed_email(order.email, order)
            except Exception:
                logger.exception("Failed MySklad status notification for order %s", changed_order_id)

        if invoice is not None:
            Order.objects.filter(ms_order_id=ms_id).exclude(invoice=invoice).update(invoice=invoice)

    return JsonResponse({"ok": True}, status=200)
