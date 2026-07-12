import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent

ENVIRONMENT = os.environ.get("DJANGO_ENV", "development").lower()
IS_PRODUCTION = ENVIRONMENT == "production"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "development-only-secret-key")
if IS_PRODUCTION and SECRET_KEY == "development-only-secret-key":
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production.")
DEBUG = os.environ.get("DJANGO_DEBUG", "false" if IS_PRODUCTION else "true").lower() == "true"
ALLOWED_HOSTS = [
    host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "catalog",
    "commerce",
    "integrations",
    "accounts",
    "content",
    "community",
    "benefits",
    "storefront",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "sequenz.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "sequenz.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SECURE = IS_PRODUCTION
CSRF_COOKIE_SECURE = IS_PRODUCTION
SECURE_SSL_REDIRECT = IS_PRODUCTION
SECURE_HSTS_SECONDS = 31_536_000 if IS_PRODUCTION else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = IS_PRODUCTION
SECURE_HSTS_PRELOAD = IS_PRODUCTION
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if IS_PRODUCTION else None
PAYMENT_PENDING_TIMEOUT_MINUTES = int(os.environ.get("PAYMENT_PENDING_TIMEOUT_MINUTES", "30"))

TOSS_CLIENT_KEY = os.environ.get("TOSS_CLIENT_KEY", "")
TOSS_SECRET_KEY = os.environ.get("TOSS_SECRET_KEY", "")
TOSS_CONFIRM_URL = os.environ.get("TOSS_CONFIRM_URL", "https://api.tosspayments.com/v1/payments/confirm")

SABANGNET_API_BASE_URL = os.environ.get("SABANGNET_API_BASE_URL", "")
SABANGNET_BEARER_TOKEN = os.environ.get("SABANGNET_BEARER_TOKEN", "")
SABANGNET_SVC_ACCOUNT_ID = os.environ.get("SABANGNET_SVC_ACCOUNT_ID", "")
SABANGNET_ORDER_STATUS_MAP = os.environ.get("SABANGNET_ORDER_STATUS_MAP", "{}")
SABANGNET_ORDER_SHIPMENT_RESPONSE_ITEMS = os.environ.get("SABANGNET_ORDER_SHIPMENT_RESPONSE_ITEMS", "[]")
SABANGNET_MALL_CONNECTION_LOGIN_ID = os.environ.get("SABANGNET_MALL_CONNECTION_LOGIN_ID", "")
SABANGNET_ACCOUNT_REGISTRATION_SERIAL = os.environ.get("SABANGNET_ACCOUNT_REGISTRATION_SERIAL", "")
