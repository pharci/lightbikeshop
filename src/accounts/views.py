# accounts/views.py — разделённые verify-вьюхи и единая проверка кода

import time
import json
import hmac
import hashlib
import urllib.parse
import re

from django.conf import settings
from django.contrib import messages, auth
from django.contrib.auth import logout, login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import (
    JsonResponse, HttpResponseBadRequest, HttpResponseRedirect, HttpResponseForbidden
)
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.crypto import constant_time_compare as ct

from cart.models import Cart, Order
from .forms import RegistrationForm, LoginForm, RecoveryForm, RecoveryInputPasswordForm
from .models import User
from .captcha import verify_recaptcha
from .utils import generate_verification_code, send_verification_code
from .security import set_action_guard, clear_action_guard, hit_rate_limit
from .telegram import _send_tg


# ===== Код: хранение/проверка =====

MAX_CODE_ATTEMPTS = 5

def _now_epoch() -> int:
    return int(time.time())

def _put_code(request, code: str, ttl_sec: int):
    s = request.session
    s['vc_code'] = str(code)
    s['vc_exp'] = _now_epoch() + int(ttl_sec)
    s['vc_try'] = 0
    s.modified = True

def _clear_code(request):
    for k in ('vc_code', 'vc_exp', 'vc_try'):
        request.session.pop(k, None)
    request.session.modified = True

def _consume_code(request, user_code: str) -> (bool, str):
    exp = int(request.session.get('vc_exp') or 0)
    if _now_epoch() > exp:
        _clear_code(request)
        return False, 'expired'
    tries = int(request.session.get('vc_try') or 0)
    if tries >= MAX_CODE_ATTEMPTS:
        _clear_code(request)
        return False, 'tries'
    stored = str(request.session.get('vc_code') or '')
    ok = ct(str(user_code or ''), stored)
    if ok:
        _clear_code(request)
        return True, 'ok'
    request.session['vc_try'] = tries + 1
    request.session.modified = True
    return False, 'mismatch'

def _flash_code_error(request, reason: str):
    if reason == 'expired':
        messages.error(request, 'Код истёк. Запросите новый.')
    elif reason == 'tries':
        messages.error(request, 'Слишком много попыток. Попробуйте позже.')
    else:
        left = max(0, MAX_CODE_ATTEMPTS - int(request.session.get('vc_try', 0)))
        messages.error(request, f'Неверный код. Осталось попыток: {left}')


# ===== Аутентификация =====

@csrf_protect
def login_view(request):
    if request.method == 'POST':
        recaptcha_response = request.POST.get('g-recaptcha-response')
        if not verify_recaptcha(recaptcha_response):
            messages.error(request, 'Подозрительная активность. Попробуйте ещё раз.')
            return redirect('accounts:login')

        form = LoginForm(request.POST)
        if not form.is_valid():
            for field, errors in form.errors.items():
                messages.error(request, f'{field}: {", ".join(errors)}')
            return redirect('accounts:login')

        email = form.cleaned_data['email']
        password = form.cleaned_data['password']

        user = authenticate(request, email=email, password=password)
        if user is None:
            messages.error(request, 'Неправильная почта или пароль.')
            return redirect('accounts:login')

        if hit_rate_limit(request, f"login_code:{email}", cooldown_sec=30):
            messages.error(request, 'Слишком часто. Попробуйте через 30 секунд.')
            return redirect('accounts:login')

        code = generate_verification_code()
        send_verification_code(email, code)

        _put_code(request, code, ttl_sec=5 * 60)
        request.session['login_user_id'] = user.id
        set_action_guard(request, 'login', ttl_minutes=30)
        return redirect('accounts:verify_login')

    context = {'form': LoginForm(), "RECAPTCHA_SITE_KEY": settings.RECAPTCHA_SITE_KEY}
    return render(request, 'accounts/login.html', context)


@csrf_protect
def verify_login(request):
    if request.method == 'POST':
        ok, reason = _consume_code(request, request.POST.get('code', '').strip())
        if ok:
            uid = request.session.pop('login_user_id', None)
            clear_action_guard(request)
            if not uid:
                return redirect('accounts:login')
            user = get_object_or_404(User, id=uid)
            login(request, user)
            return redirect('core:home')
        _flash_code_error(request, reason)
    return render(request, 'accounts/verify_code.html', {'action': 'login'})


@csrf_protect
def register_view(request):
    if request.method == 'POST':
        recaptcha_response = request.POST.get('g-recaptcha-response')
        if not verify_recaptcha(recaptcha_response):
            messages.error(request, 'Подозрительная активность. Попробуйте ещё раз.')
            return redirect('accounts:register')

        form = RegistrationForm(request.POST)
        if not form.is_valid():
            for field, errors in form.errors.items():
                messages.error(request, f'{field}: {", ".join(errors)}')
            return redirect('accounts:register')

        email = form.cleaned_data['email']
        password = form.cleaned_data['password1']

        if hit_rate_limit(request, f"reg_code:{email}", cooldown_sec=30):
            messages.error(request, 'Слишком часто. Попробуйте через 30 секунд.')
            return redirect('accounts:register')

        code = generate_verification_code()
        send_verification_code(email, code)

        _put_code(request, code, ttl_sec=5 * 60)
        request.session['reg_email'] = email
        request.session['reg_pwd_hash'] = make_password(password)
        set_action_guard(request, 'registration', ttl_minutes=30)
        return redirect('accounts:verify_register')

    context = {'form': RegistrationForm(), "RECAPTCHA_SITE_KEY": settings.RECAPTCHA_SITE_KEY}
    return render(request, 'accounts/register.html', context)


@csrf_protect
def verify_register(request):
    if request.method == 'POST':
        ok, reason = _consume_code(request, request.POST.get('code', '').strip())
        if ok:
            email = request.session.pop('reg_email', '')
            pwd_hash = request.session.pop('reg_pwd_hash', '')
            clear_action_guard(request)
            if not (email and pwd_hash):
                return redirect('accounts:register')

            user = User.objects.create_user(email=email, password='')
            user.password = pwd_hash
            user.save(update_fields=['password'])
            Cart.objects.get_or_create(user=user)

            login(request, user)
            messages.success(request, 'Регистрация завершена.')
            return redirect('accounts:profile')
        _flash_code_error(request, reason)
    return render(request, 'accounts/verify_code.html', {'action': 'registration'})


@csrf_protect
def recovery_view(request):
    if request.method == 'POST':
        recaptcha_response = request.POST.get('g-recaptcha-response')
        if not verify_recaptcha(recaptcha_response):
            messages.error(request, 'Подозрительная активность. Попробуйте ещё раз.')
            return redirect('accounts:recovery')

        form = RecoveryForm(request.POST)
        if not form.is_valid():
            for field, errors in form.errors.items():
                messages.error(request, f'{field}: {", ".join(errors)}')
            return redirect('accounts:recovery')

        email = form.cleaned_data['email']

        if hit_rate_limit(request, f"recovery_code:{email}", cooldown_sec=30):
            messages.error(request, 'Слишком часто. Попробуйте через 30 секунд.')
            return redirect('accounts:recovery')

        code = generate_verification_code()
        send_verification_code(email, code)

        _put_code(request, code, ttl_sec=5 * 60)
        request.session['recovery_email'] = email
        set_action_guard(request, 'recovery', ttl_minutes=30)
        return redirect('accounts:verify_recovery')

    context = {'form': RecoveryForm(), "RECAPTCHA_SITE_KEY": settings.RECAPTCHA_SITE_KEY}
    return render(request, 'accounts/recovery.html', context)


@csrf_protect
def verify_recovery(request):
    if request.method == 'POST':
        ok, reason = _consume_code(request, request.POST.get('code', '').strip())
        if ok:
            clear_action_guard(request)
            return redirect('accounts:recovery_input_password')
        _flash_code_error(request, reason)
    return render(request, 'accounts/verify_code.html', {'action': 'recovery'})


@csrf_protect
def recovery_input_password_view(request):
    if request.method == 'POST':
        form = RecoveryInputPasswordForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Пароли не совпадают.')
            return redirect('accounts:recovery_input_password')

        password = form.cleaned_data['password1']
        email = request.session.get('recovery_email')

        attempts = int(request.session.get('recovery_attempts', 0))
        if attempts >= 5:
            for k in ('recovery_email', 'recovery_attempts'):
                request.session.pop(k, None)
            messages.error(request, 'Слишком много попыток.')
            return redirect('accounts:recovery_input_password')

        user = User.get_user_by_email(email=email)
        if not user:
            for k in ('recovery_email', 'recovery_attempts'):
                request.session.pop(k, None)
            messages.error(request, 'Пользователь не найден.')
            return redirect('accounts:recovery')

        user.set_password(password)
        user.save(update_fields=['password'])

        authenticated = authenticate(request, email=email, password=password)
        if authenticated:
            login(request, authenticated)
            for k in ('recovery_email', 'recovery_attempts'):
                request.session.pop(k, None)
            return redirect('accounts:profile')

        messages.error(request, 'Ошибка. Попробуйте ещё раз.')
        for k in ('recovery_email', 'recovery_attempts'):
            request.session.pop(k, None)
        return redirect('accounts:recovery_input_password')

    context = {'form': RecoveryInputPasswordForm()}
    return render(request, 'accounts/recovery_input_password.html', context)


# ===== Профиль/выход =====

@login_required
def profile_view(request):
    orders = Order.objects.filter(user=request.user)
    return render(request, 'accounts/profile.html', {'user': request.user, 'orders': orders})

def logout_view(request):
    logout(request)
    return redirect('accounts:login')

# ===== Привязка e-mail =====

@login_required
@require_POST
@csrf_protect
def bind_email(request):
    email = (request.POST.get('email') or '').strip().lower()
    if not email:
        messages.error(request, "Введите e-mail.", extra_tags="email")
        return redirect('accounts:profile')
    try:
        validate_email(email)
    except ValidationError:
        messages.error(request, "Некорректный e-mail.", extra_tags="email")
        return redirect('accounts:profile')

    # мгновенная проверка занятости
    if User.objects.filter(email__iexact=email).exists():
        messages.error(request, "Этот e-mail уже занят.", extra_tags="email")
        return redirect('accounts:profile')

    if hit_rate_limit(request, f"bind_email:{email}", cooldown_sec=30):
        messages.error(request, "Слишком часто. Попробуйте через 30 секунд.", extra_tags="email")
        return redirect('accounts:profile')

    code = generate_verification_code()
    send_verification_code(email, code)

    _put_code(request, code, ttl_sec=5 * 60)
    request.session['bind_email'] = email
    set_action_guard(request, 'bind_email', ttl_minutes=30)
    return redirect('accounts:verify_bind_email')


@login_required
@csrf_protect
def verify_bind_email(request):
    if request.method == 'POST':
        ok, reason = _consume_code(request, request.POST.get('code', '').strip())
        if ok:
            email = (request.session.pop('bind_email', '') or '').strip().lower()
            clear_action_guard(request)
            if not email:
                messages.error(request, 'Не найден e-mail для привязки.')
                return redirect('accounts:profile')

            # повторно на момент подтверждения
            if User.objects.filter(email__iexact=email).exists():
                messages.error(request, 'Этот e-mail уже занят.', extra_tags='email')
                return redirect('accounts:profile')

            try:
                with transaction.atomic():
                    u = User.objects.select_for_update().get(pk=request.user.pk)
                    u.email = email
                    if hasattr(u, 'email_verified'):
                        u.email_verified = True
                    u.save(update_fields=['email'] + (['email_verified'] if hasattr(u, 'email_verified') else []))
            except IntegrityError:
                messages.error(request, 'Этот e-mail уже занят.', extra_tags='email')
                return redirect('accounts:profile')

            messages.success(request, 'E-mail привязан.')
            return redirect('accounts:profile')

        _flash_code_error(request, reason)
    return render(request, 'accounts/verify_code.html', {'action': 'bind_email'})


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

    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return HttpResponseBadRequest("Telegram bot token not configured")

    if not _verify_telegram(request, token):
        return HttpResponseForbidden("Telegram auth failed")

    tg_id = request.GET.get("id")
    if not tg_id:
        return HttpResponseBadRequest("Missing Telegram id")

    username = (request.GET.get("username") or f"user_{tg_id}")
    username = re.sub(r"[^\w\.]", "", username)[:32]

    user, created = User.objects.get_or_create(
        telegram_id=str(tg_id),
        defaults={"telegram_username": username},
    )
    if not created and username and user.telegram_username != username:
        user.telegram_username = username
        user.save(update_fields=["telegram_username"])

    login(request, user)

    if created:
        try:
            host = request.get_host()
            link = f"https://{host}"

            msg = (
                f"✨ Добро пожаловать в <a href=\"{link}\">LightBikeShop</a>!\n\n"
                "🚴 Здесь вы найдёте всё необходимое для своего велосипеда.\n"
                "🛒 Следите за обновлениями и акциями прямо в этом чате.\n\n"
                "Спасибо, что выбрали нас!"
            )
            _send_tg(tg_id, msg)
        except Exception:
            pass

    return HttpResponseRedirect(reverse("core:home"))


@login_required
def tg_link(request):
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return redirect("accounts:profile")

    if not _verify_telegram(request, token):
        messages.error(request, "Ошибка авторизации через Telegram", extra_tags="tg")
        return redirect("accounts:profile")

    tg_id = request.GET.get("id")
    if not tg_id:
        messages.error(request, "Не передан Telegram ID", extra_tags="tg")
        return redirect("accounts:profile")

    username = (request.GET.get("username") or f"user_{tg_id}")
    username = re.sub(r"[^\w\.]", "", username)[:32]

    if User.objects.filter(telegram_id=str(tg_id)).exclude(pk=request.user.pk).exists():
        messages.error(request, "Этот Telegram уже привязан к другому аккаунту", extra_tags="tg")
        return redirect("accounts:profile")

    user = request.user
    user.telegram_id = str(tg_id)
    user.telegram_username = username
    user.save(update_fields=["telegram_id", "telegram_username"])

    messages.success(request, "Telegram успешно привязан к аккаунту", extra_tags="tg")
    try:
        host = request.get_host()
        link = f"https://{host}"

        msg = (
            f"✨ Добро пожаловать в <a href=\"{link}\">LightBikeShop</a>!\n\n"
            "🚴 Здесь вы найдёте всё необходимое для своего велосипеда.\n"
            "🛒 Следите за обновлениями и акциями прямо в этом чате.\n\n"
            "Спасибо, что выбрали нас!"
        )
        _send_tg(tg_id, msg)
    except Exception:
        pass
    return redirect("accounts:profile")
