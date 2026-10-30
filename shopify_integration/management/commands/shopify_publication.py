import json
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from shopify_integration.models import ShopifyConnection
from shopify_integration.publication import prepare_publication,execute_publication
from shopify_integration.client import ShopifyError


class Command(BaseCommand):
    help = 'Explicit publish/unpublish. Requires current synchronized/reviewed products and configured publication IDs.'

    def add_arguments(self,parser):
        parser.add_argument('product_ids',nargs='+',type=int)
        group=parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--publish',action='store_true')
        group.add_argument('--unpublish',action='store_true')
        parser.add_argument('--apply',action='store_true',required=True)
        parser.add_argument('--confirm-reviewed',action='store_true',required=True)

    def handle(self,*args,**options):
        connection=ShopifyConnection.objects.filter(shop_domain=settings.SHOPIFY_SHOP_DOMAIN,enabled=True).first()
        if not connection:
            raise CommandError('Enabled connection not found.')
        for pk in options['product_ids']:
            try:
                job=prepare_publication(connection,pk,operation='publish' if options['publish'] else 'unpublish',reviewed=True)
                job=execute_publication(job.pk)
            except ShopifyError as exc:
                raise CommandError(str(exc)) from None
            self.stdout.write(json.dumps({'job':job.pk,'status':job.status,'error_code':job.error_code}))
            if job.status!='succeeded':
                raise CommandError('Publication action did not succeed. Inspect the job before retrying.')
