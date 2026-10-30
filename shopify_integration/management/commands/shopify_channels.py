import json
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from shopify_integration.models import ShopifyConnection
from shopify_integration.client import ShopifyClient,ShopifyError
from shopify_integration.publication import publications
from shopify_integration.setup import setup_webhooks


class Command(BaseCommand):
    help = 'List publications or plan/register required order webhooks.'

    def add_arguments(self,parser):
        parser.add_argument('--setup-webhooks',action='store_true')
        parser.add_argument('--apply',action='store_true')

    def handle(self,*args,**options):
        connection=ShopifyConnection.objects.filter(shop_domain=settings.SHOPIFY_SHOP_DOMAIN,enabled=True).first()
        if not connection:
            raise CommandError('Enabled connection not found.')
        try:
            result = setup_webhooks(connection,apply=options['apply']) if options['setup_webhooks'] else publications(ShopifyClient(connection))
        except ShopifyError as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(json.dumps(result,indent=2))
