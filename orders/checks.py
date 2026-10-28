from django.conf import settings
from django.core.checks import Error, register
from django.core.exceptions import ValidationError
from .stripe_config import validate


@register(deploy=True)
def stripe_configuration(app_configs, **kwargs):
    if settings.DEBUG and settings.ORDER_PAYMENT_MODE == 'demo':
        return []
    try:
        validate(require_webhook=True)
    except ValidationError as exc:
        return [Error(message, id='orders.E001') for message in exc.messages]
    return []
