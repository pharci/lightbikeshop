# accounts/views.py
import time
import json
import hmac
import hashlib
import urllib.parse
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout, login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.http import (
    JsonResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    HttpResponseForbidden,
)
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect, csrf_exempt

from cart.models import Cart
from cart.models import Order
from .forms import (
    RegistrationForm,
    LoginForm,
    RecoveryForm,
    RecoveryInputPasswordForm,
)
from .models import User
from .captcha import verify_recaptcha
from .utils import generate_verification_code, send_verification_code
from .security import (
    set_action_guard,
    clear_action_guard,
    require_action,
    hit_rate_limit,
)
from .telegram import _send_tg

# ========= вспомогательные чистилки =========

def clear_verification_session_data(request):
    for k in ("verification_code", "verification_code_exp", "user_id"):
        if k in request.session: del request.session[k]
    clear_action_guard(request)

def clear_registration_session_data(request):
    for k in ("verification_code", "verification_code_exp", "registration_email", "password_hash"):
        if k in request.session: del request.session[k]
    clear_action_guard(request)

def clear_recovery_session_data(request):
    for k in ("verification_code", "verification_code_exp", "recovery_email"):
        if k in request.session: del request.session[k]
    clear_action_guard(request)

def _now_epoch() -> int:
    return int(time.time())


# ========= АУТЕНТИФИКАЦИЯ =========

@csrf_protect
def login_view(request):
    if request.method == 'POST':
        recaptcha_response = request.POST.get('g-recaptcha-response')
        if not verify_recaptcha(recaptcha_response):
            messages.error(request, 'Извините, мы заметили подозрительную активность, попробуйте еще раз.')
            return redirect('accounts:login')

        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

            user = authenticate(request, email=email, password=password)
            if user is None:
                messages.error(request, 'Неправильная почта или пароль.')
                return redirect('accounts:login')

            # rate-limit на отправку кода (по email)
            if hit_rate_limit(request, f"login_code:{email}", cooldown_sec=30):
                messages.error(request, 'Слишком часто. Попробуйте через 30 секунд.')
                return redirect('accounts:login')

            code = generate_verification_code()
            send_verification_code(email, code)

            request.session['verification_code'] = code
            request.session['verification_code_exp'] = _now_epoch() + 5 * 60  # 5 минут
            request.session['user_id'] = user.id

            set_action_guard(request, action='login', ttl_minutes=30)
            return redirect('accounts:verify_code')
        else:
            for field, errors in form.errors.items():
                messages.error(request, f'{field}: {", ".join(errors)}')
            return redirect('accounts:login')

    else:
        form = LoginForm()

    context = {'form': form, "RECAPTCHA_SITE_KEY": settings.RECAPTCHA_SITE_KEY}
    return render(request, 'accounts/login.html', context)


@require_action({"login", "registration", "recovery"})
@csrf_protect
def verify_code(request):
    exp = int(request.session.get('verification_code_exp', 0))
    if _now_epoch() > exp:
        clear_verification_session_data(request)
        messages.error(request, 'Время проверочного кода истекло. Попробуйте получить новый.')
        return redirect('accounts:login')

    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        stored = str(request.session.get('verification_code', ''))
        attempts = int(request.session.get('verification_attempts', 0))

        if attempts >= 5:
            clear_verification_session_data(request)
            messages.error(request, 'Слишком много попыток. Попробуйте позже.')
            return redirect('accounts:login')

        if code == stored:
            action = request.session.get('action')

            if action == 'login':
                user_id = request.session.get('user_id')
                if not user_id:
                    clear_verification_session_data(request)
                    return redirect('accounts:login')
                user = get_object_or_404(User, id=user_id)
                login(request, user)
                clear_verification_session_data(request)
                return redirect('core:home')

            elif action == 'registration':
                email = request.session.get('registration_email')
                password_hash = request.session.get('password_hash')
                if not email or not password_hash:
                    clear_registration_session_data(request)
                    return redirect('accounts:register')

                user = User.objects.create_user(email=email, password='')
                user.password = password_hash
                user.save()

                Cart.objects.get_or_create(user=user)

                clear_registration_session_data(request)
                login(request, user)
                messages.success(request, 'Регистрация успешно завершена. Выполняется вход...')
                return redirect('accounts:profile')

            elif action == 'recovery':
                # просто пропускаем к вводу нового пароля
                # (email лежит в recovery_email)
                return redirect('accounts:recovery_input_password')

        else:
            request.session['verification_attempts'] = attempts + 1
            left = max(0, 5 - (attempts + 1))
            messages.error(request, f'Неправильный проверочный код. Осталось попыток: {left}')

    action = request.session.get('action')
    return render(request, 'accounts/verify_code.html', {'action': action})


@csrf_protect
def register_view(request):
    if request.method == 'POST':
        recaptcha_response = request.POST.get('g-recaptcha-response')
        if not verify_recaptcha(recaptcha_response):
            messages.error(request, 'Извините, мы заметили подозрительную активность, попробуйте еще раз.')
            return redirect('accounts:register')

        form = RegistrationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password1']

            # rate-limit на отправку кода (по email)
            if hit_rate_limit(request, f"reg_code:{email}", cooldown_sec=30):
                messages.error(request, 'Слишком часто. Попробуйте через 30 секунд.')
                return redirect('accounts:register')

            code = generate_verification_code()
            send_verification_code(email, code)

            request.session['verification_code'] = code
            request.session['verification_code_exp'] = _now_epoch() + 5 * 60
            request.session['registration_email'] = email
            request.session['password_hash'] = make_password(password)

            set_action_guard(request, action='registration', ttl_minutes=30)
            return redirect('accounts:verify_code')
        else:
            for field, errors in form.errors.items():
                messages.error(request, f'{field}: {", ".join(errors)}')
            return redirect('accounts:register')

    else:
        form = RegistrationForm()

    context = {'form': form, "RECAPTCHA_SITE_KEY": settings.RECAPTCHA_SITE_KEY}
    return render(request, 'accounts/register.html', context)


@csrf_protect
def recovery_view(request):
    if request.method == 'POST':
        recaptcha_response = request.POST.get('g-recaptcha-response')
        if not verify_recaptcha(recaptcha_response):
            messages.error(request, 'Извините, мы заметили подозрительную активность, попробуйте еще раз.')
            return redirect('accounts:recovery')

        form = RecoveryForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']

            if hit_rate_limit(request, f"recovery_code:{email}", cooldown_sec=30):
                messages.error(request, 'Слишком часто. Попробуйте через 30 секунд.')
                return redirect('accounts:recovery')

            code = generate_verification_code()
            send_verification_code(email, code)

            request.session['verification_code'] = code
            request.session['verification_code_exp'] = _now_epoch() + 5 * 60
            request.session['recovery_email'] = email

            set_action_guard(request, action='recovery', ttl_minutes=30)
            return redirect('accounts:verify_code')
        else:
            for field, errors in form.errors.items():
                messages.error(request, f'{field}: {", ".join(errors)}')
            return redirect('accounts:recovery')

    else:
        form = RecoveryForm()

    context = {'form': form, "RECAPTCHA_SITE_KEY": settings.RECAPTCHA_SITE_KEY}
    return render(request, 'accounts/recovery.html', context)


@require_action({"recovery"})
@csrf_protect
def recovery_input_password_view(request):
    if request.method == 'POST':
        form = RecoveryInputPasswordForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data['password1']
            email = request.session.get('recovery_email')

            attempts = int(request.session.get('recovery_attempts', 0))
            if attempts >= 5:
                clear_recovery_session_data(request)
                messages.error(request, 'Слишком много попыток. Попробуйте позже.')
                return redirect('accounts:recovery_input_password')

            user = User.get_user_by_email(email=email)
            if not user:
                clear_recovery_session_data(request)
                messages.error(request, 'Пользователь не найден.')
                return redirect('accounts:recovery')

            user.set_password(password)
            user.save()

            authenticated = authenticate(request, email=email, password=password)
            if authenticated:
                login(request, authenticated)
                clear_recovery_session_data(request)
                return redirect('accounts:profile')

            messages.error(request, 'Произошла ошибка, попробуйте ещё раз.')
            clear_recovery_session_data(request)
            return redirect('accounts:recovery_input_password')

        messages.error(request, 'Пароли не совпадают.')
    else:
        form = RecoveryInputPasswordForm()

    context = {'form': form}
    return render(request, 'accounts/recovery_input_password.html', context)


@login_required
def profile_view(request):
    user = request.user
    orders = Order.objects.filter(user=user)
    return render(request, 'accounts/profile.html', {'user': user, 'orders': orders})


def logout_view(request):
    logout(request)
    return redirect('accounts:login')


def check_email_availability(request):
    if request.method == 'POST' and request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            email = (data.get('email') or '').strip()
        except Exception:
            return JsonResponse({'is_taken': False})
        return JsonResponse({'is_taken': User.objects.filter(email=email).exists()})


# ========= TELEGRAM LOGIN =========

def _verify_telegram(request, bot_token: str) -> bool:
    qs = request.META.get("QUERY_STRING", "")
    try:
        q = urllib.parse.parse_qs(qs, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return False

    tg_hash = (q.pop("hash", [None])[0])
    if not tg_hash:
        return False

    # data_check_string
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
    # строже окно: 10 минут, и не позже на 60 сек
    if auth_date > now + 60 or now - auth_date > 600:
        return False

    return True


@csrf_exempt
def tg_auth(request):
    if request.method != "GET":
        return HttpResponseBadRequest("Method not allowed")

    token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    if not token:
        return HttpResponseBadRequest("Telegram bot token not configured")

    if not _verify_telegram(request, token):
        return HttpResponseForbidden("Telegram auth failed")

    tg_id = request.GET.get("id")
    if not tg_id:
        return HttpResponseBadRequest("Missing Telegram id")

    username = (request.GET.get("username") or f"user_{tg_id}")
    # лёгкая санация username (латиница/цифры/подчёркивание/точка), до 32 символов
    username = re.sub(r"[^\w\.]", "", username)[:32]

    user, created = User.objects.get_or_create(
        telegram_id=str(tg_id),
        defaults={"telegram_username": username},
    )
    # если уже был, но имя изменилось — можно обновить
    if not created and username and user.telegram_username != username:
        user.telegram_username = username
        user.save(update_fields=["telegram_username"])

    login(request, user)

    if created:
        try:
            _send_tg(tg_id, "Добро пожаловать в магазин lightbikeshop.ru!")
        except Exception:
            pass

    return HttpResponseRedirect(reverse("core:home"))