from celery import shared_task
from django.db.models import Q
from django.utils import timezone
from .draft_sync import execute_draft
from .models import ShopifySyncJob


@shared_task
def run_draft_job(job_id):
    operation = ShopifySyncJob.objects.get(pk=job_id).operation
    if operation in ('publish','unpublish'):
        from .publication import execute_publication
        job = execute_publication(job_id)
    else:
        job = execute_draft(job_id)
    return {'id': job.pk, 'status': job.status, 'error_code': job.error_code}


@shared_task
def dispatch_draft_jobs():
    from .models import ShopifyCatalogueBatch
    for pk in ShopifyCatalogueBatch.objects.filter(status='pending').values_list('pk', flat=True)[:2]:
        prepare_catalogue_batch.apply_async(args=[pk], queue='shopify')
    pending = ShopifySyncJob.objects.filter(operation__in=['draft_sync','publish','unpublish']).filter(
        Q(status='pending') | Q(status='retry', next_retry_at__lte=timezone.now()))
    for pk in pending.order_by('pk').values_list('pk', flat=True)[:20]:
        run_draft_job.apply_async(args=[pk], queue='shopify')


@shared_task
def prepare_catalogue_batch(batch_id):
    """Prepare a durable, resumable page locally; existing workers perform API writes."""
    from django.db import transaction
    from django.core.exceptions import ValidationError
    from catalog.models import Product
    from .models import ShopifyCatalogueBatch, ShopifyProductMapping, IntegrationLog
    from .services import dry_run
    from .draft_sync import prepare_draft, check_enabled
    from .client import ShopifyError
    check_enabled()
    with transaction.atomic():
        batch = ShopifyCatalogueBatch.objects.select_for_update(of=('self',)).select_related('connection', 'actor').get(pk=batch_id)
        if batch.status != 'pending':
            return
        if not batch.connection.enabled or not batch.actor or not batch.actor.is_active or not batch.actor.is_staff or not batch.actor.has_perm('shopify_integration.sync_shopify_draft'):
            batch.status = 'stopped'
            batch.save(update_fields=['status', 'updated_at'])
            return
        products = list(Product.objects.filter(pk__gt=batch.last_product_id, is_published=True,
                        is_archived=False).order_by('pk')[:20])
        for product in products:
            report = dry_run(product, batch.connection)
            if report['errors']:
                batch.skipped += 1
                IntegrationLog.objects.create(connection=batch.connection, product=product,
                    operation='bulk_sync', status='skipped', codes=report['errors'])
            else:
                mapping = ShopifyProductMapping.objects.filter(connection=batch.connection, product=product).first()
                if mapping and mapping.remote_product_gid and mapping.payload_hash == report['payload_hash'] and mapping.status in ('draft_synced', 'published', 'active_synced', 'unpublished'):
                    mapping.auto_sync = True
                    mapping.save(update_fields=['auto_sync'])
                    batch.unchanged += 1
                else:
                    try:
                        with transaction.atomic():
                            prepare_draft(batch.connection, product.pk, actor=batch.actor)
                        batch.queued += 1
                    except (ValidationError, ShopifyError):
                        batch.skipped += 1
                        IntegrationLog.objects.create(connection=batch.connection, product=product,
                            operation='bulk_sync', status='skipped', codes=['preparation_failed'])
            batch.last_product_id = product.pk
        if len(products) < 20:
            batch.status = 'prepared'
        batch.save()


@shared_task
def process_webhook(receipt_id):
    from .webhooks import process_receipt
    receipt = process_receipt(receipt_id)
    return {'id':receipt.pk,'status':receipt.status,'error_code':receipt.error_code}


@shared_task
def dispatch_webhooks():
    from django.conf import settings
    from .models import ShopifyWebhookReceipt
    if not settings.SHOPIFY_ENABLED or not settings.SHOPIFY_ORDER_IMPORT_ENABLED:
        return
    pending = ShopifyWebhookReceipt.objects.filter(connection__enabled=True,connection__import_orders_enabled=True).filter(
        Q(status='pending') | Q(status='retry',next_retry_at__lte=timezone.now()))
    for pk in pending.order_by('pk').values_list('pk',flat=True)[:30]:
        process_webhook.apply_async(args=[pk],queue='shopify')


@shared_task
def sync_managed_products():
    from django.conf import settings
    from .models import ShopifyProductMapping
    from .services import dry_run
    from .draft_sync import prepare_draft
    if not settings.SHOPIFY_AUTO_SYNC_ENABLED or not settings.SHOPIFY_DRAFT_SYNC_ENABLED:
        return
    mappings = ShopifyProductMapping.objects.filter(auto_sync=True,connection__enabled=True,
        status__in=['draft_synced','published','unpublished','active_synced']).select_related('connection','product')
    for mapping in mappings.iterator():
        report = dry_run(mapping.product,mapping.connection)
        if report['errors']:
            ShopifyProductMapping.objects.filter(pk=mapping.pk).update(error_code='local_validation_failed')
            continue
        if report['payload_hash'] != mapping.payload_hash:
            job = prepare_draft(mapping.connection,mapping.product_id)
            run_draft_job.apply_async(args=[job.pk],queue='shopify')
        elif mapping.error_code=='local_validation_failed':
            ShopifyProductMapping.objects.filter(pk=mapping.pk).update(error_code='')


@shared_task
def reconcile_orders():
    from django.conf import settings
    from .models import ShopifyConnection
    from .order_import import reconcile
    from .client import ShopifyError
    from .models import IntegrationLog
    if not settings.SHOPIFY_ORDER_IMPORT_ENABLED or not settings.SHOPIFY_ENABLED:
        return
    for connection in ShopifyConnection.objects.filter(enabled=True,import_orders_enabled=True):
        try:
            reconcile(connection)
        except Exception as exc:
            code = str(exc)[:60] if isinstance(exc,ShopifyError) else 'order_reconciliation_failed'
            IntegrationLog.objects.create(connection=connection,operation='order_reconciliation',status='failed',codes=[code])


@shared_task
def retry_order_mapping(mapping_id):
    from .models import ShopifyOrderMapping
    from .order_import import import_order
    mapping = ShopifyOrderMapping.objects.select_related('connection').get(pk=mapping_id)
    result = import_order(mapping.connection,mapping.remote_order_gid)
    return {'id':result.pk,'status':result.status}


@shared_task
def expire_private_snapshots():
    from datetime import timedelta
    from .models import ShopifyOrderMapping,ShopifyWebhookReceipt
    boundary = timezone.now()-timedelta(days=90)
    ShopifyOrderMapping.objects.filter(snapshot_saved_at__lt=boundary).exclude(payload_encrypted='').update(payload_encrypted='')
    ShopifyWebhookReceipt.objects.filter(processed_at__lt=boundary,status__in=['processed','quarantined']).delete()
