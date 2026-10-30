"""Shared settings; deployment-specific choices live in separate modules."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(Path(os.environ.get("DJANGO_ENV_FILE", str(BASE_DIR / ".env"))))

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
DEBUG = False
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",") if host.strip()]
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()]
INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "web.apps.WebConfig",
    "cms.apps.CmsConfig",
    "catalog.apps.CatalogConfig",
    "delivery.apps.DeliveryConfig",
    "orders.apps.OrdersConfig",
    "shopify_integration.apps.ShopifyIntegrationConfig",
    "channels",
    "customers.apps.CustomersConfig",
    "allauth", "allauth.account", "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "customers.middleware.AuthenticationProtectionMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "customers.context_processors.authentication",
        "catalog.context_processors.storefront_categories",
        "cms.context_processors.contact_settings",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": os.getenv("POSTGRES_DB", "terai_food"),
    "USER": os.getenv("POSTGRES_USER", "terai"),
    "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
    "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
    "PORT": os.getenv("POSTGRES_PORT", "5432"),
    "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
    "CONN_HEALTH_CHECKS": True,
    "OPTIONS": {"connect_timeout": 5, "sslmode": os.getenv("POSTGRES_SSLMODE", "prefer")},
}}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Europe/London"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
from .accounts import *  # noqa: F403,E402

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
from .content import *  # noqa: F403,E402
from .orders import *  # noqa: F403,E402
from .shopify import *  # noqa: F403,E402
