from django.urls import include, re_path, path

from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('recovery/', views.recovery_view, name='recovery'),
    path('verify_code/', views.verify_code, name='verify_code'),
    path('recovery_input_password/', views.recovery_input_password_view, name='recovery_input_password'),
    path('check_email_availability/', views.check_email_availability, name='check_email_availability'),
]