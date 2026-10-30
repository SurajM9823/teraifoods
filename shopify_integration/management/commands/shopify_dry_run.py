import json

from django.core.management.base import BaseCommand, CommandError

from catalog.models import Product
from shopify_integration.models import ShopifyConnection
from shopify_integration.services import dry_run


class Command(BaseCommand):
    help = 'Preview Shopify changes locally as JSON. Makes no network requests. No credentials required.'

    def add_arguments(self, parser):
        parser.add_argument('product_ids', nargs='+', type=int)
        parser.add_argument('--shop', help='Optional existing connection domain for last-applied comparison.')

    def handle(self, *args, **options):
        connection = None
        if options['shop']:
            connection = ShopifyConnection.objects.filter(shop_domain=options['shop']).first()
            if connection is None:
                raise CommandError('Shopify connection not found.')
        products = {p.pk: p for p in Product.objects.filter(pk__in=options['product_ids'])}
        missing = set(options['product_ids']) - products.keys()
        if missing:
            raise CommandError('Unknown product IDs: ' + ', '.join(map(str, sorted(missing))))
        reports = [dry_run(products[pk], connection) for pk in options['product_ids']]
        self.stdout.write(json.dumps(reports, indent=2, ensure_ascii=False))
