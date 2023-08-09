from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import logout, login, authenticate

from .forms import RegistrationForm, LoginForm, VerificationCodeForm, RecoveryForm, RecoveryInputPasswordForm

from django.http import JsonResponse
import json

from .models import Order, OrderItem, User
from cart.models import Cart

from .captcha import verify_recaptcha
from .utils import generate_verification_code, send_verification_code

import datetime
from datetime import timedelta
from django.utils import timezone

from django.contrib.auth.hashers import make_password, check_password
from django.middleware import csrf
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required

from .security import generate_token, check_token

from django.conf import settings
@csrf_protect
def login_view(request):

    if request.method == 'POST':

        recaptcha_response = request.POST.get('g-recaptcha-response')

        print(recaptcha_response)

        if verify_recaptcha(recaptcha_response):

            form = LoginForm(request.POST)

            if form.is_valid():
                email = form.cleaned_data['email']
                password = form.cleaned_data['password']
                
                user = authenticate(request, email=email, password=password)
                if user is not None:
                    # Проверяем, есть ли уже ограничение на ввод кода
                    if request.session.get('verification_attempts', 0) >= 5:

                        messages.error(request, 'Слишком много попыток. Попробуйте позже.')
                        return redirect('accounts:login')

                    verification_code = generate_verification_code()
                    send_verification_code(email, verification_code)

                    request.session['verification_code'] = verification_code
                    request.session['verification_code_expiration'] = str(timezone.now() + timezone.timedelta(minutes=5))
                    request.session['user_id'] = user.id

                    generate_token(request, 'login')

                    return redirect('accounts:verify_code_login')
                else:
                    messages.error(request, 'Неправильная почта или пароль.')
                    return redirect('accounts:login')
            else:
                for field, errors in form.errors.items():
                    messages.error(request, f'{field}: {", ".join(errors)}')
                return redirect('accounts:login')
        else:
            messages.error(request, 'Извините, мы заметили подозрительную активность, попробуйте еще раз.')
            return redirect('accounts:login')
    else:
        form = LoginForm(request)
    
    context = {'form': form, "RECAPTCHA_SITE_KEY": settings.RECAPTCHA_SITE_KEY}
    return render(request, 'accounts/login.html', context)

@check_token
@csrf_protect
def verify_code_login_view(request):
    
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('accounts:login')
    
    user = User.objects.get(id=user_id)

    # Проверяем, истекло ли время действия кода
    verification_code_expiration = datetime.datetime.strptime(request.session.get('verification_code_expiration'), '%Y-%m-%d %H:%M:%S.%f%z')
    if timezone.now() > verification_code_expiration:
        del request.session['verification_code']
        del request.session['verification_code_expiration']
        del request.session['user_id']
        messages.error(request, 'Время проверочного кода истекло. Попробуйте получить новый.')
        return redirect('accounts:login')

    if request.method == 'POST':
        code = request.POST.get('code')
        stored_code = request.session.get('verification_code')

        # Проверяем, сколько попыток ввода кода уже было
        verification_attempts = request.session.get('verification_attempts', 0)

        if verification_attempts >= 5:

            request.session.set_expiry(timedelta(minutes=30))

            messages.error(request, 'Слишком много попыток. Попробуйте позже.')
            return redirect('accounts:login')

        if code == stored_code:

            # Успешная аутентификация
            login(request, user)
            del request.session['verification_code']
            del request.session['verification_code_expiration']
            del request.session['user_id']

            return redirect('store:news')
        else:

            # Неверный код, увеличиваем счетчик попыток
            request.session['verification_attempts'] = verification_attempts + 1
            messages.error(request, 'Неправильный проверочный код. Осталось попыток: {}'.format(5 - verification_attempts))
            return redirect('accounts:verify_code_login')

    return render(request, 'accounts/verify_code_login.html')


@csrf_protect
def register_view(request):
    if request.method == 'POST':

        recaptcha_response = request.POST.get('g-recaptcha-response')

        if verify_recaptcha(recaptcha_response):

            form = RegistrationForm(request.POST)

            if form.is_valid():
                email = form.cleaned_data['email']
                password = form.cleaned_data['password1']
                
                # Проверяем, есть ли уже ограничение на регистрацию
                if request.session.get('registration_attempts', 0) >= 5:
                    messages.error(request, 'Слишком много попыток. Попробуйте позже.')
                    return redirect('accounts:register')

                verification_code = generate_verification_code()
                send_verification_code(email, verification_code)

                request.session['verification_code'] = verification_code
                request.session['verification_code_expiration'] = str(timezone.now() + timedelta(minutes=5))
                request.session['registration_email'] = email
                request.session['password_hash'] = make_password(password)

                generate_token(request, 'register')

                return redirect('accounts:verify_code_registration')

            else:
                for field, errors in form.errors.items():
                    messages.error(request, f'{field}: {", ".join(errors)}')
                return redirect('accounts:register')

        else:
            messages.error(request, 'Извините, мы заметили подозрительную активность, попробуйте еще раз.')
            return redirect('accounts:login')

    else:
        form = RegistrationForm()
    
    context = {'form': form, "RECAPTCHA_SITE_KEY": settings.RECAPTCHA_SITE_KEY}
    return render(request, 'accounts/register.html', context)

@check_token
@csrf_protect
def verify_code_registration_view(request):
    email = request.session.get('registration_email')
    password_hash = request.session.get('password_hash')
    if not email:
        return redirect('accounts:register')
    
    # Проверяем, истекло ли время действия кода
    verification_code_expiration = datetime.datetime.strptime(request.session.get('verification_code_expiration'), '%Y-%m-%d %H:%M:%S.%f%z')
    if timezone.now() > verification_code_expiration:
        del request.session['verification_code']
        del request.session['verification_code_expiration']
        del request.session['registration_email']
        del request.session['password_hash']
        messages.error(request, 'Время проверочного кода истекло. Попробуйте зарегистрироваться позже.')
        return redirect('accounts:register')
    
    if request.method == 'POST':
        form = VerificationCodeForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            stored_code = request.session.get('verification_code')

            # Проверяем, сколько попыток ввода кода уже было
            verification_attempts = request.session.get('verification_attempts', 0)
            if verification_attempts >= 5:
                del request.session['verification_code']
                del request.session['verification_code_expiration']
                del request.session['registration_email']
                del request.session['password_hash']
                messages.error(request, 'Слишком много попыток. Попробуйте зарегистрироваться позже.')
                return redirect('accounts:register')

            if code == stored_code:
                # Успешная регистрация

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
                
                del request.session['verification_code']
                del request.session['verification_code_expiration']
                del request.session['registration_email']
                del request.session['password_hash']

                login(request, user)

                messages.success(request, 'Регистрация успешно завершена. Выполняется вход...')

                return redirect('accounts:profile')
            else:
                # Неверный код, увеличиваем счетчик попыток
                request.session['verification_attempts'] = verification_attempts + 1
                messages.error(request, 'Неправильный проверочный код. Осталось попыток: {}'.format(5 - verification_attempts))
                return redirect('accounts:verify_code_registration')
    else:
        form = VerificationCodeForm()
    
    context = {'form': form}
    return render(request, 'accounts/verify_code_registration.html', context)


@csrf_protect
def recovery_view(request):
    if request.method == 'POST':

        recaptcha_response = request.POST.get('g-recaptcha-response')

        if verify_recaptcha(recaptcha_response):

            form = RecoveryForm(request.POST)

            if form.is_valid():
                email = form.cleaned_data['email']
                
                # Проверяем, есть ли уже ограничение на восстановление пароля
                if request.session.get('registration_attempts', 0) >= 5:
                    messages.error(request, 'Слишком много попыток. Попробуйте позже.')
                    return redirect('accounts:register')

                verification_code = generate_verification_code()
                send_verification_code(email, verification_code)

                request.session['verification_code'] = verification_code
                request.session['verification_code_expiration'] = str(timezone.now() + timedelta(minutes=5))
                request.session['recovery_email'] = email

                generate_token(request, 'recovery')

                return redirect('accounts:verify_code_recovery')

            else:
                for field, errors in form.errors.items():
                    messages.error(request, f'{field}: {", ".join(errors)}')
                return redirect('accounts:recovery')

        else:
            messages.error(request, 'Извините, мы заметили подозрительную активность, попробуйте еще раз.')
            return redirect('accounts:login')

    else:
        form = RecoveryForm()
    
    context = {'form': form, "RECAPTCHA_SITE_KEY": settings.RECAPTCHA_SITE_KEY}
    return render(request, 'accounts/recovery.html', context)


@check_token
@csrf_protect
def verify_code_recovery_view(request):
    email = request.session.get('recovery_email')

    if not email:
        return redirect('accounts:recovery')
    
    # Проверяем, истекло ли время действия кода
    verification_code_expiration = datetime.datetime.strptime(request.session.get('verification_code_expiration'), '%Y-%m-%d %H:%M:%S.%f%z')
    if timezone.now() > verification_code_expiration:
        del request.session['verification_code']
        del request.session['verification_code_expiration']
        del request.session['recovery_email']

        messages.error(request, 'Время проверочного кода истекло. Попробуйте еще раз.')
        return redirect('accounts:recovery')
    
    if request.method == 'POST':
        form = VerificationCodeForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            stored_code = request.session.get('verification_code')

            verification_attempts = request.session.get('verification_attempts', 0)

            if verification_attempts >= 5:
                del request.session['verification_code']
                del request.session['verification_code_expiration']
                del request.session['recovery_email']
                messages.error(request, 'Слишком много попыток. Попробуйте позже.')
                return redirect('accounts:recovery')

            if code == stored_code:

                del request.session['verification_code']
                del request.session['verification_code_expiration']

                messages.success(request, 'Осталось только ввести новый пароль...')

                return redirect('accounts:recovery_input_password')
            else:
                # Неверный код, увеличиваем счетчик попыток
                request.session['verification_attempts'] = verification_attempts + 1
                messages.error(request, 'Неправильный проверочный код. Осталось попыток: {}'.format(5 - verification_attempts))
                return redirect('accounts:verify_code_recovery')
    else:
        form = VerificationCodeForm()
    
    context = {'form': form}
    return render(request, 'accounts/verify_code_recovery.html', context)

@check_token
@csrf_protect
def recovery_input_password_view(request):
    if request.method == 'POST':

        form = RecoveryInputPasswordForm(request.POST)

        if form.is_valid():
            password = form.cleaned_data['password1']
            email = request.session.get('recovery_email')
            
            # Проверяем, есть ли уже ограничение на восстановление пароля
            if request.session.get('registration_attempts', 0) >= 5:
                messages.error(request, 'Слишком много попыток. Попробуйте позже.')
                return redirect('accounts:recovery')

            user = User.get_user_by_email(email=email)

            if user is not None:

                user.set_password(password)
                user = authenticate(request, email=email, password=password)
                login(request, user)

            else:

                messages.error(request, 'Произошла ошибка, попробуйте еще раз.')
                return redirect('accounts:recovery')

            del request.session['recovery_email']

            return redirect('accounts:profile')

        else:
            messages.error(request, 'Пароли не совпадают.')

            return redirect('accounts:recovery_input_password')

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