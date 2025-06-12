from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import logout, login, authenticate
from django.http import JsonResponse
import json
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password

from .forms import (
    RegistrationForm,
    LoginForm,
    VerificationCodeForm,
    RecoveryForm,
    RecoveryInputPasswordForm,
)
from .models import Order, User
from cart.models import Cart
from .captcha import verify_recaptcha
from .utils import generate_verification_code, send_verification_code
from .security import generate_token, check_token
from django.conf import settings

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

            if user is not None:
                verification_code = generate_verification_code()
                send_verification_code(email, verification_code)

                request.session['verification_code'] = verification_code
                request.session['verification_code_expiration'] = str(timezone.now() + timezone.timedelta(minutes=5))
                request.session['user_id'] = user.id
                request.session['action'] = 'login'

                generate_token(request, 'login')

                return redirect('accounts:verify_code')
            else:
                messages.error(request, 'Неправильная почта или пароль.')
        else:
            for field, errors in form.errors.items():
                messages.error(request, f'{field}: {", ".join(errors)}')
    else:
        form = LoginForm()

    context = {'form': form, "RECAPTCHA_SITE_KEY": settings.RECAPTCHA_SITE_KEY}
    return render(request, 'accounts/login.html', context)

@check_token
@csrf_protect
def verify_code(request):
    verification_code_expiration = timezone.datetime.strptime(request.session.get('verification_code_expiration'), '%Y-%m-%d %H:%M:%S.%f%z')

    if timezone.now() > verification_code_expiration:
        clear_verification_session_data(request)
        messages.error(request, 'Время проверочного кода истекло. Попробуйте получить новый.')
        return redirect('accounts:login')

    if request.method == 'POST':
        code = request.POST.get('code')
        stored_code = request.session.get('verification_code')
        verification_attempts = request.session.get('verification_attempts', 0)

        if verification_attempts >= 5:
            clear_verification_session_data(request)
            messages.error(request, 'Слишком много попыток. Попробуйте позже.')
            return redirect('accounts:login')

        if code == stored_code:
            action = request.session.get('action')

            if action == 'login':
                user_id = request.session.get('user_id')
                if user_id:
                    user = User.objects.get(id=user_id)
                    login(request, user)
                    clear_verification_session_data(request)
                    return redirect('store:news')
                else:
                    return redirect('accounts:login')

            elif action == 'registration':
                email = request.session.get('registration_email')
                password_hash = request.session.get('password_hash')

                user = User.objects.create_user(email=email, password='')
                user.set_unusable_password()
                user.password = password_hash
                user.save()

                cart = Cart.objects.create(user=user)
                cart.save()

                order_id = request.session.get('order_id')
                if order_id:
                    order = Order.objects.get(order_id=order_id)
                    order.user = user
                    order.save()
                    del request.session['order_id']

                clear_verification_session_data(request)
                login(request, user)
                messages.success(request, 'Регистрация успешно завершена. Выполняется вход...')
                return redirect('accounts:profile')

            elif action == 'recovery':
                clear_verification_session_data(request)
                messages.success(request, 'Осталось только ввести новый пароль...')
                return redirect('accounts:recovery_input_password')
        else:
            request.session['verification_attempts'] = verification_attempts + 1
            attempts_left = 5 - verification_attempts
            messages.error(request, f'Неправильный проверочный код. Осталось попыток: {attempts_left}')

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

            registration_attempts = request.session.get('registration_attempts', 0)
            if registration_attempts >= 5:
                clear_registration_session_data(request)
                messages.error(request, 'Слишком много попыток. Попробуйте позже.')
                return redirect('accounts:register')

            verification_code = generate_verification_code()
            send_verification_code(email, verification_code)

            request.session['verification_code'] = verification_code
            request.session['verification_code_expiration'] = str(timezone.now() + timezone.timedelta(minutes=5))
            request.session['registration_email'] = email
            request.session['password_hash'] = make_password(password)
            request.session['action'] = 'registration'

            generate_token(request, 'register')

            return redirect('accounts:verify_code')
        else:
            for field, errors in form.errors.items():
                messages.error(request, f'{field}: {", ".join(errors)}')
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

            recovery_attempts = request.session.get('recovery_attempts', 0)
            if recovery_attempts >= 5:
                clear_recovery_session_data(request)
                messages.error(request, 'Слишком много попыток. Попробуйте позже.')
                return redirect('accounts:recovery')

            verification_code = generate_verification_code()
            send_verification_code(email, verification_code)

            request.session['verification_code'] = verification_code
            request.session['verification_code_expiration'] = str(timezone.now() + timezone.timedelta(minutes=5))
            request.session['recovery_email'] = email
            request.session['action'] = 'recovery'

            generate_token(request, 'recovery')

            return redirect('accounts:verify_code')
        else:
            for field, errors in form.errors.items():
                messages.error(request, f'{field}: {", ".join(errors)}')
    else:
        form = RecoveryForm()

    context = {'form': form, "RECAPTCHA_SITE_KEY": settings.RECAPTCHA_SITE_KEY}
    return render(request, 'accounts/recovery.html', context)

@check_token
@csrf_protect
def recovery_input_password_view(request):
    if request.method == 'POST':
        form = RecoveryInputPasswordForm(request.POST)

        if form.is_valid():
            password = form.cleaned_data['password1']
            email = request.session.get('recovery_email')

            recovery_attempts = request.session.get('recovery_attempts', 0)
            if recovery_attempts >= 5:
                clear_recovery_session_data(request)
                messages.error(request, 'Слишком много попыток. Попробуйте позже.')
                return redirect('accounts:recovery_input_password')

            user = User.get_user_by_email(email=email)

            if user:
                user.set_password(password)
                user.save()
                authenticated_user = authenticate(request, email=email, password=password)

                if authenticated_user:
                    login(request, authenticated_user)
                    clear_recovery_session_data(request)
                    return redirect('accounts:profile')
                else:
                    messages.error(request, 'Произошла ошибка, попробуйте еще раз.')
            else:
                messages.error(request, 'Произошла ошибка, попробуйте еще раз.')

            clear_recovery_session_data(request)
            return redirect('accounts:recovery_input_password')
        else:
            messages.error(request, 'Пароли не совпадают.')

    else:
        form = RecoveryInputPasswordForm()

    context = {'form': form}
    return render(request, 'accounts/recovery_input_password.html', context)

@login_required
def profile_view(request):
    user = request.user
    orders = Order.objects.filter(user=user)
    context = {'user': user, 'orders': orders}
    return render(request, 'accounts/profile.html', context)

def logout_view(request):
    logout(request)
    return redirect('accounts:login')

def check_email_availability(request):
    if request.method == 'POST' and request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
        data = json.loads(request.body)
        email = data.get('email')
        data = {
            'is_taken': User.objects.filter(email=email).exists()
        }
        return JsonResponse(data)


def clear_verification_session_data(request):
    if 'verification_code' in request.session:
        del request.session['verification_code']
    if 'verification_code_expiration' in request.session:
        del request.session['verification_code_expiration']
    if 'user_id' in request.session:
        del request.session['user_id']
    if 'action' in request.session:
        del request.session['action']

def clear_registration_session_data(request):
    if 'verification_code' in request.session:
        del request.session['verification_code']
    if 'verification_code_expiration' in request.session:
        del request.session['verification_code_expiration']
    if 'registration_email' in request.session:
        del request.session['registration_email']
    if 'password_hash' in request.session:
        del request.session['password_hash']
    if 'action' in request.session:
        del request.session['action']

def clear_recovery_session_data(request):
    if 'verification_code' in request.session:
        del request.session['verification_code']
    if 'verification_code_expiration' in request.session:
        del request.session['verification_code_expiration']
    if 'recovery_email' in request.session:
        del request.session['recovery_email']
    if 'action' in request.session:
        del request.session['action']