"""Local validation only: never include credential values in diagnostics."""
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError


def mode():
    if settings.STRIPE_MODE not in ('test', 'live'):
        raise ValidationError('Set STRIPE_MODE explicitly to test or live.')
    return settings.STRIPE_MODE


def validate(require_webhook=False):
    selected = mode()
    if settings.ORDER_PAYMENT_MODE != 'stripe':
        raise ValidationError('Stripe payments are disabled.')
    pairs = [('publishable', settings.STRIPE_PUBLISHABLE_KEY, (f'pk_{selected}_',)),
             ('secret', settings.STRIPE_SECRET_KEY, (f'sk_{selected}_', f'rk_{selected}_'))]
    for label, value, prefixes in pairs:
        if not any(value.startswith(prefix) and len(value) > len(prefix) for prefix in prefixes) or '...' in value:
            raise ValidationError(f'Stripe {selected} {label} key is missing or mismatched.')
    if require_webhook or selected == 'live':
        secret = settings.STRIPE_WEBHOOK_SECRET
        if not secret.startswith('whsec_') or len(secret) <= 6 or '...' in secret:
            raise ValidationError('Stripe webhook signing secret is missing or invalid.')
    if selected == 'live':
        origin = urlsplit(settings.ORDER_PUBLIC_ORIGIN)
        if (origin.scheme != 'https' or not origin.hostname or origin.username or origin.password
                or origin.path or origin.query or origin.fragment):
            raise ValidationError('Live Stripe payments require an HTTPS ORDER_PUBLIC_ORIGIN without a path.')


def validate_payment(payment):
    if payment.stripe_mode != mode():
        raise ValidationError('This payment belongs to a different Stripe mode. Contact support.')
