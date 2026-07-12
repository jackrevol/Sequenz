import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, "true" if default else "false").lower() in {"1", "true", "yes", "on"}

ENVIRONMENT = os.environ.get("DJANGO_ENV", "development").lower()
IS_PRODUCTION = ENVIRONMENT == "production"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "development-only-secret-key")
if IS_PRODUCTION and SECRET_KEY == "development-only-secret-key":
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production.")
DEBUG = env_bool("DJANGO_DEBUG", not IS_PRODUCTION)
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
if IS_PRODUCTION:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

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
        "NAME": Path(os.environ.get("DJANGO_DB_PATH", BASE_DIR / "db.sqlite3")),
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

STATIC_URL = "/static/"
STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles"))
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("DJANGO_MEDIA_ROOT", BASE_DIR / "media"))
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if IS_PRODUCTION
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        )
    },
}
SERVE_MEDIA_FILES = env_bool("DJANGO_SERVE_MEDIA_FILES", DEBUG)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", IS_PRODUCTION)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", IS_PRODUCTION)
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", IS_PRODUCTION)
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000" if IS_PRODUCTION else "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", IS_PRODUCTION)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", IS_PRODUCTION)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if IS_PRODUCTION else None
PAYMENT_PENDING_TIMEOUT_MINUTES = int(os.environ.get("PAYMENT_PENDING_TIMEOUT_MINUTES", "30"))

TOSS_CLIENT_KEY = os.environ.get("TOSS_CLIENT_KEY", "")
TOSS_SECRET_KEY = os.environ.get("TOSS_SECRET_KEY", "")
TOSS_CONFIRM_URL = os.environ.get("TOSS_CONFIRM_URL", "https://api.tosspayments.com/v1/payments/confirm")

SABANGNET_API_BASE_URL = os.environ.get("SABANGNET_API_BASE_URL", "")
SABANGNET_CLIENT_ID = os.environ.get("SABANGNET_CLIENT_ID", "b3e3cdb2-de0e-4fd8-99c2-e9ad995c5401")
SABANGNET_CLIENT_SECRET = os.environ.get("SABANGNET_CLIENT_SECRET", "$2a$10$gQrOTxi6PvteD6SShn0Fk.")
SABANGNET_BEARER_TOKEN = os.environ.get("SABANGNET_BEARER_TOKEN", "")
SABANGNET_SVC_ACCOUNT_ID = os.environ.get("SABANGNET_SVC_ACCOUNT_ID", "")
SABANGNET_ORDER_STATUS_MAP = os.environ.get("SABANGNET_ORDER_STATUS_MAP", "{}")
SABANGNET_ORDER_SHIPMENT_RESPONSE_ITEMS = os.environ.get("SABANGNET_ORDER_SHIPMENT_RESPONSE_ITEMS", "[]")
SABANGNET_MALL_CONNECTION_LOGIN_ID = os.environ.get("SABANGNET_MALL_CONNECTION_LOGIN_ID", "")
SABANGNET_ACCOUNT_REGISTRATION_SERIAL = os.environ.get("SABANGNET_ACCOUNT_REGISTRATION_SERIAL", "")
