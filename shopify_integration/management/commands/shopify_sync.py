import json
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from shopify_integration.models import ShopifyConnection
from shopify_integration.draft_sync import prepare_draft, execute_draft
from shopify_integration.client import ShopifyError


class Command(BaseCommand):
    help = 'Synchronize catalogue data; new products remain drafts. Publication state never changes.'

    def add_arguments(self, parser):
        parser.add_argument('product_ids', nargs='+', type=int)
        parser.add_argument('--apply', action='store_true', required=True, help='Confirm catalogue writes; use shopify_dry_run first.')

    def handle(self, *args, **options):
        connection = ShopifyConnection.objects.filter(shop_domain=settings.SHOPIFY_SHOP_DOMAIN, enabled=True).first()
        if connection is None:
            raise CommandError('Enabled Shopify connection not found.')
        failed = False
        for product_id in options['product_ids']:
            try:
                job = execute_draft(prepare_draft(connection, product_id).pk)
            except (ShopifyError, ValidationError) as exc:
                raise CommandError(str(exc)) from None
            self.stdout.write(json.dumps({'product_id': product_id, 'job': job.pk, 'status': job.status,
                'error_code': job.error_code, 'remote_product_gid': job.mapping.remote_product_gid}))
            failed |= job.status != 'succeeded'
        if failed:
            raise CommandError('Some drafts did not finish; inspect integration jobs/logs before retrying.')
