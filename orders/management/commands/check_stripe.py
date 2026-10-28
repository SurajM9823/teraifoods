from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from orders.models import Payment, Refund
from orders.stripe_config import validate


class Command(BaseCommand):
    help = 'Validate selected Stripe configuration locally; never calls Stripe or prints secrets.'

    def handle(self, *args, **options):
        try:
            validate(require_webhook=True)
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages)) from None
        self.stdout.write(f'Stripe mode: {settings.STRIPE_MODE}')
        self.stdout.write('Selected credential prefixes and origin: valid (not API authentication).')
        self.stdout.write('Stripe account ownership, permissions and webhook delivery: not verified by this command.')
        self.stdout.write(f'Other-mode payment records: {Payment.objects.exclude(stripe_mode=settings.STRIPE_MODE).count()}')
        self.stdout.write(f'Other-mode pending reservations: {Payment.objects.exclude(stripe_mode=settings.STRIPE_MODE).filter(order__payment_method="stripe", order__fulfilment_status="pending_payment").count()}')
        self.stdout.write(f'Other-mode pending refunds: {Refund.objects.exclude(order__payment__stripe_mode=settings.STRIPE_MODE).filter(status__in=("pending", "requires_action")).count()}')
