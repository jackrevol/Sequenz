import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, "true" if default else "false").lower() in {"1", "true", "yes", "on"}

ENVIRONMENT = os.environ.get("DJANGO_ENV", "development").lower()
IS_PRODUCTION = ENVIRONMENT == "production"
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "752abe3d345a06a79ebdbe0a4166d2f48c911fd2c59a500e2f4a90dfa1414ed2bda4ecbcd7cc8bb6beb5b6928047aea0",
)
DEBUG = env_bool("DJANGO_DEBUG", not IS_PRODUCTION)
ALLOWED_HOSTS = [
    host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if host.strip()
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

def database_config(environment=None):
    environment = environment if environment is not None else os.environ
    mysql_values = {
        "DB_HOST": environment.get("DB_HOST", "").strip(),
        "DB_PORT": environment.get("DB_PORT", "").strip(),
        "DB_NAME": environment.get("DB_NAME", "").strip(),
        "DB_USER": environment.get("DB_USER", "").strip(),
        "DB_PASSWORD": environment.get("DB_PASSWORD", ""),
    }
    configured = {key for key, value in mysql_values.items() if value}
    if not configured:
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": Path(environment.get("DJANGO_DB_PATH", BASE_DIR / "db.sqlite3")),
        }

    missing = [key for key, value in mysql_values.items() if not value]
    if missing:
        raise ImproperlyConfigured(f"Incomplete MySQL configuration: {', '.join(missing)}")

    try:
        port = int(mysql_values["DB_PORT"])
    except ValueError as exc:
        raise ImproperlyConfigured("DB_PORT must be an integer.") from exc

    return {
        "ENGINE": "django.db.backends.mysql",
        "HOST": mysql_values["DB_HOST"],
        "PORT": port,
        "NAME": mysql_values["DB_NAME"],
        "USER": mysql_values["DB_USER"],
        "PASSWORD": mysql_values["DB_PASSWORD"],
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }


DATABASES = {"default": database_config()}

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
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if IS_PRODUCTION else None
PAYMENT_PENDING_TIMEOUT_MINUTES = int(os.environ.get("PAYMENT_PENDING_TIMEOUT_MINUTES", "30"))

TOSS_CLIENT_KEY = os.environ.get("TOSS_CLIENT_KEY", "")
TOSS_SECRET_KEY = os.environ.get("TOSS_SECRET_KEY", "")
TOSS_CONFIRM_URL = os.environ.get("TOSS_CONFIRM_URL", "https://api.tosspayments.com/v1/payments/confirm")

SABANGNET_AUTH_MODE = os.environ.get("SABANGNET_AUTH_MODE", "PRODUCTION").upper()
SABANGNET_BASE_URLS = {
    "PRODUCTION": "https://api.sabangnet.co.kr",
    "SANDBOX": "https://sandbox.sabangnet.co.kr",
}
SABANGNET_API_BASE_URL = SABANGNET_BASE_URLS.get(SABANGNET_AUTH_MODE, "")
SABANGNET_TOKEN_URL = f"{SABANGNET_API_BASE_URL}/oauth2/token" if SABANGNET_API_BASE_URL else ""
SABANGNET_CLIENT_ID = os.environ.get("SABANGNET_CLIENT_ID", "")
SABANGNET_CLIENT_SECRET = os.environ.get("SABANGNET_CLIENT_SECRET", "")
SABANGNET_CLIENT_TYPE = os.environ.get("SABANGNET_CLIENT_TYPE", "SB_APP")
SABANGNET_BEARER_TOKEN = os.environ.get("SABANGNET_BEARER_TOKEN", "")
SABANGNET_SVC_ACCOUNT_ID = os.environ.get("SABANGNET_SVC_ACCOUNT_ID", "")
SABANGNET_TIMEOUT_SECONDS = int(os.environ.get("SABANGNET_TIMEOUT_SECONDS", "30"))
SABANGNET_VERIFY_SSL = env_bool("SABANGNET_VERIFY_SSL", True)
SABANGNET_ORDER_STATUS_MAP = os.environ.get("SABANGNET_ORDER_STATUS_MAP", "{}")
SABANGNET_ORDER_SHIPMENT_RESPONSE_ITEMS = os.environ.get("SABANGNET_ORDER_SHIPMENT_RESPONSE_ITEMS", "[]")
SABANGNET_MALL_CONNECTION_LOGIN_ID = os.environ.get("SABANGNET_MALL_CONNECTION_LOGIN_ID", "")
SABANGNET_ACCOUNT_REGISTRATION_SERIAL = os.environ.get("SABANGNET_ACCOUNT_REGISTRATION_SERIAL", "")
