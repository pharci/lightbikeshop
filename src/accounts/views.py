import time, hmac, hashlib, urllib.parse, re

from django.conf import settings
from core.integrations import integration_value
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseRedirect, HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError

from .otp import gen_code, current_id
from .models import EmailOTP, User
from cart.models import Order
from cart.adopt import adopt_session_cart
from .utils import verify_recaptcha
from .telegram import _send_tg
from .email import send_verification_code

def _norm_email(s: str) -> str:
    s = (s or "").strip().lower()
    try:
        validate_email(s)
        return s
    except ValidationError:
        return ""

@never_cache
@ensure_csrf_cookie
def login_view(request):
    if request.method == "GET":
        return render(request, "accounts/login.html", {"RECAPTCHA_SITE_KEY": integration_value("RECAPTCHA_SITE_KEY")})
    return redirect("accounts:login")

@require_POST
@csrf_protect
def api_send_code(request):
    email = _norm_email(request.POST.get("email"))
    recaptcha = request.POST.get("g-recaptcha-response")
    agree = request.POST.get("agree") == "1"

    if not email:
        return JsonResponse({"ok": False, "error": "invalid_email"}, status=400)
    if not verify_recaptcha(recaptcha):
        return JsonResponse({"ok": False, "error": "recaptcha"}, status=400)

    exists = User.objects.filter(email=email).exists()
    if not exists and not agree:
        return JsonResponse({"ok": False, "error": "need_consent"}, status=400)

    code = gen_code(6)
    try:
        send_verification_code(email, code)
    except Exception:
        return JsonResponse({"ok": False, "error": "send_fail"}, status=502)

    sid = current_id()
    req = EmailOTP.create_for_email(
        email=email, code=code, secret_id=sid,
        ip=request.META.get("REMOTE_ADDR"),
        ua=request.META.get("HTTP_USER_AGENT", "")[:255],
    )

    request.session["otp_email"] = email
    request.session["otp_req_id"] = str(req.request_id)
    request.session["otp_allow_signup"] = bool(agree)
    return JsonResponse({"ok": True, "request_id": str(req.request_id)})

@require_POST
@csrf_protect
def api_verify_code(request):
    email = _norm_email(request.POST.get("email") or request.session.get("otp_email"))
    request_id = request.POST.get("request_id") or request.session.get("otp_req_id")
    code = (request.POST.get("code") or "").strip()
    if not (email and request_id and code):
        return JsonResponse({"ok": False, "error": "missing"}, status=400)

    try:
        otp = EmailOTP.objects.get(request_id=request_id, email=email)
    except EmailOTP.DoesNotExist:
        return JsonResponse({"ok": False, "error": "not_found"}, status=404)
    if not otp.can_verify():
        return JsonResponse({"ok": False, "error": "expired_or_locked"}, status=400)
    if not otp.verify_and_consume(code):
        return JsonResponse({"ok": False, "error": "bad_code", "attempts_left": max(0, otp.max_attempts - otp.attempts)}, status=400)

    user = User.objects.filter(email=email).first()
    if user is None:
        if not request.session.get("otp_allow_signup"):
            return JsonResponse({"ok": False, "error": "signup_not_allowed"}, status=403)
        user = User.objects.create_user(
            email=email,
            is_active=True,
        )
        adopt_session_cart(request, user)

    if not user.is_active:
        return JsonResponse({"ok": False, "error": "inactive"}, status=403)
    login(request, user)
    # очистить одноразовые флаги
    for k in ("otp_email","otp_req_id","otp_allow_signup"):
        request.session.pop(k, None)
    return JsonResponse({"ok": True, "redirect": "/"})


# ===== Профиль/выход =====

@login_required
def profile_view(request):
    orders = Order.objects.filter(user=request.user)
    return render(request, 'accounts/profile.html', {'user': request.user, 'orders': orders})

def logout_view(request):
    logout(request)
    return redirect('accounts:login')

# ===== Telegram Login =====

def _verify_telegram(request, bot_token: str) -> bool:
    qs = request.META.get("QUERY_STRING", "")
    try:
        q = urllib.parse.parse_qs(qs, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return False

    tg_hash = (q.pop("hash", [None])[0])
    if not tg_hash:
        return False

    dcs = "\n".join(f"{k}={q[k][0]}" for k in sorted(q.keys()))
    secret = hashlib.sha256(bot_token.encode()).digest()
    calc = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, tg_hash):
        return False

    try:
        auth_date = int(q.get("auth_date", ["0"])[0])
    except ValueError:
        return False

    now = int(time.time())
    if auth_date > now + 60 or now - auth_date > 600:
        return False

    return True

@csrf_exempt
def tg_auth(request):
    if request.method != "GET":
        return HttpResponseBadRequest("Method not allowed")

    token = integration_value("TELEGRAM_BOT_TOKEN")
    if not token:
        return HttpResponseBadRequest("Telegram bot token not configured")

    if not _verify_telegram(request, token):
        return HttpResponseForbidden("Telegram auth failed")

    tg_id = request.GET.get("id")
    if not tg_id:
        return HttpResponseBadRequest("Missing Telegram id")

    # TTL защиты от повторов
    try:
        auth_ts = int(request.GET.get("auth_date", "0"))
    except ValueError:
        return HttpResponseBadRequest("Bad auth_date")
    if abs(int(time.time()) - auth_ts) > 300:
        return HttpResponseForbidden("Telegram auth too old")

    username = request.GET.get("username") or None
    first_name = request.GET.get("first_name") or ""
    last_name = request.GET.get("last_name") or ""

    # атомарно + без email
    with transaction.atomic():
        user, created = User.objects.select_for_update().get_or_create(
            telegram_id=str(tg_id),
            defaults={
                "email": None,
                "telegram_username": username,
                "first_name": first_name,
                "last_name": last_name,
            },
        )
        # мягкое обновление профиля при повторном входе
        dirty = False
        if not created:
            if username and username != user.telegram_username:
                user.telegram_username = username; dirty = True
            if first_name != user.first_name:
                user.first_name = first_name; dirty = True
            if last_name != user.last_name:
                user.last_name = last_name; dirty = True
            if user.email == "":  # защита от старых данных
                user.email = None; dirty = True
            if dirty:
                user.save(update_fields=["telegram_username","first_name","last_name","email"])

    # явный backend
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")

    if created:
        try:
            # формируем валидную https-ссылку
            host = request.get_host()
            link = f"https://{host}"
            msg = (
                f"✨ Добро пожаловать в <a href=\"{link}\">LightBikeShop</a>!\n\n"
                "🚴 Здесь вы найдёте всё необходимое для своего велосипеда.\n"
                "🛒 Следите за обновлениями и акциями прямо в этом чате.\n\n"
                "Спасибо, что выбрали нас!"
            )
            _send_tg(tg_id, msg)  # parse_mode=HTML внутри функции
        except Exception:
            pass

    return HttpResponseRedirect(reverse("core:home"))


@login_required
def tg_link(request):
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    if not token:
        messages.error(request, "Telegram токен не настроен", extra_tags="tg")
        return redirect("accounts:profile")

    if not _verify_telegram(request, token):
        messages.error(request, "Ошибка авторизации через Telegram", extra_tags="tg")
        return redirect("accounts:profile")

    tg_id = request.GET.get("id")
    if not tg_id:
        messages.error(request, "Не передан Telegram ID", extra_tags="tg")
        return redirect("accounts:profile")

    # TTL от повторов
    try:
        auth_ts = int(request.GET.get("auth_date", "0"))
    except ValueError:
        messages.error(request, "Некорректный auth_date", extra_tags="tg")
        return redirect("accounts:profile")
    if abs(int(time.time()) - auth_ts) > 300:
        messages.error(request, "Просроченная авторизация через Telegram", extra_tags="tg")
        return redirect("accounts:profile")

    # Валидный username по правилам Telegram
    raw_username = request.GET.get("username") or ""
    username = re.sub(r"[^A-Za-z0-9_]", "", raw_username)[:32]
    if len(username) < 5:
        username = f"user_{tg_id}"[:32]

    # Защита от гонки и дубликатов
    try:
        with transaction.atomic():
            if User.objects.filter(telegram_id=str(tg_id)).exclude(pk=request.user.pk).exists():
                messages.error(request, "Этот Telegram уже привязан к другому аккаунту", extra_tags="tg")
                return redirect("accounts:profile")

            user = request.user
            user.telegram_id = str(tg_id)
            user.telegram_username = username
            user.save(update_fields=["telegram_id", "telegram_username"])
    except IntegrityError:
        messages.error(request, "Этот Telegram уже привязан к другому аккаунту", extra_tags="tg")
        return redirect("accounts:profile")

    messages.success(request, "Telegram успешно привязан к аккаунту", extra_tags="tg")

    try:
        base = getattr(settings, "SITE_URL", None)
        link = (base or request.build_absolute_uri("/")).rstrip("/")
        msg = (
            f"✨ Добро пожаловать в <a href=\"{link}\">LightBikeShop</a>!\n\n"
            "🚴 Здесь вы найдёте всё необходимое для своего велосипеда.\n"
            "🛒 Следите за обновлениями и акциями прямо в этом чате.\n\n"
            "Спасибо, что выбрали нас!"
        )
        _send_tg(tg_id, msg)  # внутри должен быть parse_mode=HTML
    except Exception:
        pass

    return redirect("accounts:profile")
