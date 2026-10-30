import json
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from shopify_integration.models import ShopifyConnection
from shopify_integration.order_import import import_order
from shopify_integration.client import ShopifyError


class Command(BaseCommand):
    help = 'Explicitly import/reconcile one Shopify order. Does not charge, refund or adjust stock.'

    def add_arguments(self,parser):
        parser.add_argument('order_gid')
        parser.add_argument('--apply',action='store_true',required=True)
        parser.add_argument('--allow-historical',action='store_true',help='Explicitly permit an order created before imports were enabled.')

    def handle(self,*args,**options):
        connection=ShopifyConnection.objects.filter(shop_domain=settings.SHOPIFY_SHOP_DOMAIN,enabled=True).first()
        if not connection:
            raise CommandError('Enabled connection not found.')
        try:
            mapping=import_order(connection,options['order_gid'],allow_historical=options['allow_historical'])
        except ShopifyError as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(json.dumps({'mapping':mapping.pk,'status':mapping.status,'error_code':mapping.error_code}))
        if mapping.status!='imported':
            raise CommandError('Order quarantined for review; no partial operational order was imported.')
