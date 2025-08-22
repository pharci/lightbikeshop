import os
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import urlparse

# ──────────────────────────────────────────────────────────────────────────────
# Base
# ──────────────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")  # грузим .env из корня проекта

# ──────────────────────────────────────────────────────────────────────────────
# Helpers (кастеры из env)
# ──────────────────────────────────────────────────────────────────────────────
def env_str(key: str, default: str | None = None) -> str | None:
    return os.getenv(key, default)

def env_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")

def env_int(key: str, default: int | None = None) -> int | None:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default

def env_list(key: str, default: list[str] | None = None) -> list[str]:
    val = os.getenv(key)
    if not val:
        return default or []
    # поддержка списков через запятую и переносы строк
    raw = [x.strip() for x in val.replace("\n", ",").split(",")]
    return [x for x in raw if x]

# ──────────────────────────────────────────────────────────────────────────────
# Core security
# ──────────────────────────────────────────────────────────────────────────────
DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = env_str("DJANGO_SECRET_KEY")
if not DEBUG and not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be set in production")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", [])

# ──────────────────────────────────────────────────────────────────────────────
# Apps
# ──────────────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    # 3rd-party UI/admin
    "admin_interface",
    "django_jsonform",
    "rangefilter",
    "django_admin_logs",
    "column_toggle",
    "colorfield",
    "nested_admin",
    "adminsortable2",

    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Project apps
    "core",
    "products",
    "accounts",
    "cart",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    # твои middlewares
    "accounts.middlewares.LoginValidationMiddleware",
    "accounts.middlewares.RegisterValidationMiddleware",
]

ROOT_URLCONF = "lightbikeshop.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.breadcrumbs",
            ],
        },
    },
]

WSGI_APPLICATION = "lightbikeshop.wsgi.application"

# ──────────────────────────────────────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────────────────────────────────────
# Поддержка DATABASE_URL (postgres://user:pass@host:5432/dbname). Если не задан — sqlite.
DATABASE_URL = env_str("DATABASE_URL", "")
if DATABASE_URL:
    # Простой парсер без сторонних библиотек
    u = urlparse(DATABASE_URL)
    ENGINE_MAP = {
        "postgres": "django.db.backends.postgresql",
        "postgresql": "django.db.backends.postgresql",
        "postgresql_psycopg2": "django.db.backends.postgresql",
        "psql": "django.db.backends.postgresql",
        "mysql": "django.db.backends.mysql",
        "sqlite": "django.db.backends.sqlite3",
        "sqlite3": "django.db.backends.sqlite3",
    }
    ENGINE = ENGINE_MAP.get(u.scheme, "django.db.backends.postgresql")
    DB_NAME = (u.path or "").lstrip("/") or env_str("DB_NAME", "")
    DATABASES = {
        "default": {
            "ENGINE": ENGINE,
            "NAME": DB_NAME,
            "USER": u.username or "",
            "PASSWORD": u.password or "",
            "HOST": u.hostname or "",
            "PORT": str(u.port or ""),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ──────────────────────────────────────────────────────────────────────────────
# Authentication / User model
# ──────────────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ──────────────────────────────────────────────────────────────────────────────
# i18n / tz
# ──────────────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = env_str("DJANGO_LANGUAGE_CODE", "ru")
TIME_ZONE = env_str("DJANGO_TIME_ZONE", "Europe/Moscow")
USE_I18N = True
USE_L10N = True
USE_TZ = True
USE_THOUSAND_SEPARATOR = True
THOUSAND_SEPARATOR = '\u202F'  # узкий неразрывный пробел
NUMBER_GROUPING = 3

# ──────────────────────────────────────────────────────────────────────────────
# Static & Media
# ──────────────────────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ──────────────────────────────────────────────────────────────────────────────
# Email (SMTP)
# ──────────────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = env_str("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env_str("EMAIL_HOST", "")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = env_str("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env_str("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
DEFAULT_FROM_EMAIL = env_str("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)

# ──────────────────────────────────────────────────────────────────────────────
# ReCAPTCHA
# ──────────────────────────────────────────────────────────────────────────────
RECAPTCHA_SITE_KEY = env_str("RECAPTCHA_SITE_KEY", "")
RECAPTCHA_SECRET_KEY = env_str("RECAPTCHA_SECRET_KEY", "")

# ──────────────────────────────────────────────────────────────────────────────
# Telegram и токены
# ──────────────────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = env_str("TELEGRAM_BOT_TOKEN", "")
DADATA_TOKEN = env_str("DADATA_TOKEN", "")

# ──────────────────────────────────────────────────────────────────────────────
# PAYMENTS
# ──────────────────────────────────────────────────────────────────────────────
T_BANK_TERMINAL_KEY = env_str("T_BANK_TERMINAL_KEY", "")
T_BANK_PASSWORD = env_str("T_BANK_PASSWORD", "")
T_BANK_BASE_URL = env_str("T_BANK_BASE_URL", "https://rest-api-test.tinkoff.ru/v2")
# ──────────────────────────────────────────────────────────────────────────────
# SDEK
# ──────────────────────────────────────────────────────────────────────────────
CDEK_BASE = os.getenv("CDEK_BASE", "https://api.edu.cdek.ru")  # prod: https://api.cdek.ru
CDEK_ID = os.environ["CDEK_ID"]      
CDEK_SECRET = os.environ["CDEK_SECRET"]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "cdek-cache",
    }
}

# ──────────────────────────────────────────────────────────────────────────────
# Security headers & cookies (адекватные дефолты)
# ──────────────────────────────────────────────────────────────────────────────
SECURE_CROSS_ORIGIN_OPENER_POLICY = env_str("SECURE_COOP", "*")

val = env_str("SECURE_PROXY_SSL_HEADER", "")
if val:
    try:
        name, hdr_val = [x.strip() for x in val.split(",", 1)]
        SECURE_PROXY_SSL_HEADER = (
            name if name.startswith("HTTP_")
            else f"HTTP_{name.upper().replace('-', '_')}",
            hdr_val
        )
    except ValueError:
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  # дефолт

USE_X_FORWARDED_HOST = env_bool("USE_X_FORWARDED_HOST", True)

SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE   = env_bool("CSRF_COOKIE_SECURE", not DEBUG)
SESSION_COOKIE_HTTPONLY = env_bool("SESSION_COOKIE_HTTPONLY", True)
CSRF_COOKIE_HTTPONLY    = env_bool("CSRF_COOKIE_HTTPONLY", False)  # обычно False, чтобы формы работали
SESSION_COOKIE_SAMESITE = env_str("SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE    = env_str("CSRF_COOKIE_SAMESITE", "Lax")

SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", not DEBUG)
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31536000 if not DEBUG else 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", not DEBUG)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", not DEBUG)
X_FRAME_OPTIONS = env_str("X_FRAME_OPTIONS", "DENY")

# ──────────────────────────────────────────────────────────────────────────────
# Logging (красиво в консоль)
# ──────────────────────────────────────────────────────────────────────────────
LOG_LEVEL = env_str("DJANGO_LOG_LEVEL", "INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "clean": {
            "format": "[{levelname}] {asctime} {name}: {message}",
            "style": "{",
        },
        "simple": {"format": "[{levelname}] {message}", "style": "{"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "clean",
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "accounts": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}