from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from catalog.models import Product
from catalog.services import adjust_stock


class Command(BaseCommand):
    help = 'Set sample stock for uncounted imported products in local development only.'

    def handle(self, *args, **options):
        if not settings.DEBUG or settings.ORDER_PAYMENT_MODE != 'demo':
            raise CommandError('Requires DEBUG and ORDER_PAYMENT_MODE=demo; never run for production inventory.')
        count = 0
        for product in Product.objects.filter(stock_confirmed=False, is_published=True):
            adjust_stock(product.pk, 20, reason='Local demo inventory, not a real warehouse count', actor=None,
                         key=f'demo-initial:{product.pk}', kind='initial')
            count += 1
        self.stdout.write(f'Added audited sample inventory to {count} previously uncounted products.')
