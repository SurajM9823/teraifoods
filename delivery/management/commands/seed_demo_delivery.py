from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from delivery.models import WeightBand


class Command(BaseCommand):
    help = 'Add sample local-development delivery rates without replacing existing bands.'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Sample delivery rates are only permitted in DEBUG development environments.')
        for grams,charge in [(500,'2.99'),(1000,'3.99'),(2000,'5.49'),(5000,'7.99'),(10000,'11.99'),(20000,'17.99')]:
            _,created = WeightBand.objects.get_or_create(max_weight_grams=grams,defaults={'charge':charge})
            self.stdout.write(f'Up to {grams} gm: '+('sample rate added' if created else 'existing rate preserved'))
