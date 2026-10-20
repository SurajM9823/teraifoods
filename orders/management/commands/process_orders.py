from django.core.management.base import BaseCommand
from orders.tasks import dispatch_pending, expire_reservations


class Command(BaseCommand):
    help = 'Run one recovery pass for expired reservations, order events and refunds; emails use Celery.'

    def handle(self, *args, **options):
        expire_reservations()
        dispatch_pending()
        self.stdout.write('Order recovery pass completed; inspect worker logs for provider retries.')
