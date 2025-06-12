import os
import locale

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = 'z+ksf@)0d^qojbh4rnp4b1to$hq&*tt(3bs$gf(3i267g$k9ln'

RECAPTCHA_SITE_KEY = "6LdY2X8nAAAAAGuFqEOrAok4NdW8jWjhaQDNY4Vh"
RECAPTCHA_SECRET_KEY = "6LdY2X8nAAAAAG5hXbq6_3vIeiAc2d-idi488mzo"

TELEGRAM_BOT_TOKEN = '7980167640:AAGBAN3gO3Fifvl5cOcdgXuLve3e9TBSvoo'

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.beget.com'
EMAIL_PORT = 2525
EMAIL_HOST_USER = 'support@lightbikeshop.ru'
EMAIL_HOST_PASSWORD = 'SBT*Llb4'
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

AUTH_USER_MODEL = 'accounts.User'

DEBUG = True

CSRF_COOKIE_SECURE = True
ALLOWED_HOSTS = ['*', 'lightbikeshop.ru', 'www.lightbikeshop.ru', 'localhost']
CSRF_TRUSTED_ORIGINS = [
    'https://lightbikeshop.ru',
]

INSTALLED_APPS = [
    "admin_interface",
    "django_jsonform",
    "rangefilter",
    "django_admin_logs",
    "column_toggle",
    "colorfield",
    "nested_admin",
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'main',
    'store',
    'products',
    'accounts',
    'cart',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'accounts.middlewares.LoginValidationMiddleware',
    'accounts.middlewares.RegisterValidationMiddleware',
]

ROOT_URLCONF = 'lightbikeshop.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'main.context_processors.navbar',
            ],
        },
    },
]

WSGI_APPLICATION = 'lightbikeshop.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]
LANGUAGE_CODE = 'ru-RU'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')   