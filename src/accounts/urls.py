from django.urls import include, re_path, path

from . import views

urlpatterns = [
    # аутентификация
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register_view, name="register"),
    path("recovery/", views.recovery_view, name="recovery"),
    path("recovery/input-password/", views.recovery_input_password_view, name="recovery_input_password"),

    # verify-коды
    path("verify/login/", views.verify_login, name="verify_login"),
    path("verify/register/", views.verify_register, name="verify_register"),
    path("verify/recovery/", views.verify_recovery, name="verify_recovery"),
    path("verify/bind-email/", views.verify_bind_email, name="verify_bind_email"),

    # профиль
    path("profile/", views.profile_view, name="profile"),
    path("bind-email/", views.bind_email, name="bind_email"),
    
    # telegram
    path("tg/auth/", views.tg_auth, name="tg_auth"),
    path("tg/link/", views.tg_link, name="tg_link"),
]