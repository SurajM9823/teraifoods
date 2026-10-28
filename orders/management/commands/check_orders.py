from django.conf import settings
from django.core.management.base import BaseCommand
from catalog.models import Product, Order
from delivery.models import WeightBand
from orders.models import Notification, Refund


class Command(BaseCommand):
    help = 'Report order setup and pending work without printing secrets or changing data.'

    def handle(self, *args, **options):
        values = {
            'Effective payment mode':'local demo' if settings.DEBUG and settings.ORDER_PAYMENT_MODE == 'demo' else 'Stripe ' + (settings.STRIPE_MODE or 'UNCONFIGURED'),
            'Products':Product.objects.count(),
            'Products with confirmed stock':Product.objects.filter(stock_confirmed=True).count(),
            'Active delivery bands':WeightBand.objects.filter(is_active=True).count(),
            'Stripe selected key configured':settings.STRIPE_SECRET_KEY.startswith((f'sk_{settings.STRIPE_MODE}_',f'rk_{settings.STRIPE_MODE}_')),
            'Stripe webhook configured':bool(settings.STRIPE_WEBHOOK_SECRET),
            'Orders':Order.objects.count(),
            'Pending notifications':Notification.objects.exclude(status='sent').count(),
            'Pending refunds':Refund.objects.filter(status='pending').count(),
            'Online return window (days)':settings.ORDER_RETURN_DAYS,
        }
        for name,value in values.items():
            self.stdout.write(f'{name}: {value}')
