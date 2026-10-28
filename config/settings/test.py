"""Explicit SQLite-only fast checks when a PostgreSQL server is unavailable.

Normal development and production always use PostgreSQL. Run the normal test
suite against PostgreSQL too before deployment; this module is not a fallback.
"""
from .development import *  # noqa: F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
EMAIL_DELIVERY_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
ALLAUTH_TRUSTED_PROXY_COUNT = 0
CHANNEL_LAYERS = {'default': {'BACKEND':'channels.layers.InMemoryChannelLayer'}}
ORDER_PAYMENT_MODE = 'stripe'
STRIPE_MODE = 'test'
