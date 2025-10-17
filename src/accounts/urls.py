from django.urls import include, re_path, path

from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("api/auth/send_code/", views.api_send_code, name="api_send_code"),
    path("api/auth/verify_code/", views.api_verify_code, name="api_verify_code"),

    path("profile/", views.profile_view, name="profile"),
    path("tg/auth/", views.tg_auth, name="tg_auth"),
    path("tg/link/", views.tg_link, name="tg_link"),
]