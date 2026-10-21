from django.conf import settings


def authentication(request):
    return {"google_login_enabled": settings.GOOGLE_LOGIN_ENABLED,
            "order_demo_payments":settings.DEBUG and settings.ORDER_PAYMENT_MODE == 'demo'}
