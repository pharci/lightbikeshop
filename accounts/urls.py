from django.urls import include, re_path, path

from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('recovery/', views.recovery_view, name='recovery'),
    path('verify_code_login/', views.verify_code_login_view, name='verify_code_login'),
    path('verify_code_registration/', views.verify_code_registration_view, name='verify_code_registration'),
    path('verify_code_recovery/', views.verify_code_recovery_view, name='verify_code_recovery'),
    path('recovery_input_password/', views.recovery_input_password_view, name='recovery_input_password'),
    path('check_email_availability/', views.check_email_availability, name='check_email_availability'),
]