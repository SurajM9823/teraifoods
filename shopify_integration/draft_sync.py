"""Explicit draft catalogue synchronization; never calls checkout, stock or payment services."""
from datetime import timedelta
from decimal import Decimal
import logging
import time
import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from catalog.models import Product
from .client import ShopifyClient, ShopifyError
from .graphql import SCOPES_QUERY, FILES_QUERY, FILE_QUERY, PRODUCT_SNAPSHOT, FILE_CREATE, PRODUCT_SET
from .models import (ShopifyProductMapping, ShopifyVariantMapping, ShopifyMediaMapping,
                     ShopifySyncJob, IntegrationLog)
from .services import dry_run

logger = logging.getLogger(__name__)


def check_enabled():
    if not settings.SHOPIFY_ENABLED or not settings.SHOPIFY_DRAFT_SYNC_ENABLED:
        raise ShopifyError('draft_sync_disabled')


def prepare_draft(connection, product_id, *, actor=None):
    check_enabled()
    if not connection.enabled or connection.shop_domain != settings.SHOPIFY_SHOP_DOMAIN:
        raise ShopifyError('connection_disabled_or_mismatched')
    if actor is not None and (not actor.is_active or not actor.is_staff or
            not actor.has_perm('shopify_integration.sync_shopify_draft')):
        raise PermissionDenied
    report = dry_run(Product.objects.get(pk=product_id), connection)
    if report['errors']:
        raise ValidationError(report['errors'])
    with transaction.atomic():
        mapping, _ = ShopifyProductMapping.objects.get_or_create(connection=connection, product_id=product_id)
        mapping = ShopifyProductMapping.objects.select_for_update().get(pk=mapping.pk)
        existing = ShopifySyncJob.objects.filter(mapping=mapping, operation='draft_sync',
            status__in=['pending', 'retry', 'running']).order_by('pk').first()
        if existing:
            return existing
        mapping.desired_revision += 1
        mapping.status = 'queued'
        mapping.save(update_fields=['desired_revision', 'status', 'updated_at'])
        return ShopifySyncJob.objects.create(mapping=mapping, operation='draft_sync',
            desired_revision=mapping.desired_revision, idempotency_key=uuid.uuid4().hex)


def preflight(client):
    data = client.query(SCOPES_QUERY)
    if data['shop']['currencyCode'] != 'GBP':
        raise ShopifyError('shop_currency_mismatch')
    scopes = {scope['handle'] for scope in data['currentAppInstallation']['accessScopes']}
    if not {'write_products', 'write_files'}.issubset(scopes):
        raise ShopifyError('missing_write_products_or_write_files_scope')


def snapshot(client, identifier):
    after, product, variants = None, None, []
    for _ in range(21):
        current = client.query(PRODUCT_SNAPSHOT, {'identifier': identifier, 'after': after})['productByIdentifier']
        if current is None:
            return None
        product = current
        variants.extend(current['variants']['nodes'])
        page = current['variants']['pageInfo']
        if not page['hasNextPage']:
            product['variant_nodes'] = variants
            if current['media']['pageInfo']['hasNextPage']:
                raise ShopifyError('remote_media_limit_requires_review')
            return product
        if not page['endCursor'] or page['endCursor'] == after:
            break
        after = page['endCursor']
    raise ShopifyError('remote_variant_pagination_incomplete')


def owned_draft(remote, product_id, *, allow_active=False):
    if remote:
        if not remote.get('metafield') or remote['metafield']['value'] != str(product_id):
            raise ShopifyError('remote_product_not_django_managed')
        if remote['status'] != 'DRAFT' and not (allow_active and remote['status']=='ACTIVE'):
            raise ShopifyError('remote_product_not_draft')


def selections(variant):
    return variant['optionValues'] or [{'name': 'Title', 'value': 'Default Title'}]


def combination(values):
    return tuple((value['name'], value['value']) for value in values)


def ensure_media(client, mapping, image):
    record, _ = ShopifyMediaMapping.objects.get_or_create(product_mapping=mapping,
        image_id=image['django_image_id'], defaults={'digest': image['digest']})
    if record.digest != image['digest']:
        record.remote_file_gid = ''
        record.digest = image['digest']
    if not record.remote_file_gid:
        filename = f"teraifoods-{mapping.product_id}-{image['django_image_id']}-{image['digest']}.jpg"
        found = client.query(FILES_QUERY, {'query': f'filename:{filename}'})['files']['nodes']
        if len(found) > 1:
            raise ShopifyError('ambiguous_media_file')
        if found:
            file = found[0]
        else:
            result = client.mutate(FILE_CREATE, {'files': [{
                'originalSource': image['url'], 'contentType': 'IMAGE', 'alt': image['alt'],
                'filename': filename, 'duplicateResolutionMode': 'RAISE_ERROR',
            }]})
            if len(result.get('files') or []) != 1:
                raise ShopifyError('invalid_media_response')
            file = result['files'][0]
        record.remote_file_gid = file['id']
        record.status = file['fileStatus'].lower()
        record.save()
    for attempt in range(5):
        file = client.query(FILE_QUERY, {'id': record.remote_file_gid})['node']
        if not file or file['fileStatus'] == 'FAILED':
            raise ShopifyError('media_failed_or_missing')
        if file['fileStatus'] == 'READY':
            record.status = 'ready'
            record.save(update_fields=['status'])
            return record.remote_file_gid
        if attempt < 4:
            time.sleep(2)
    raise ShopifyError('media_processing_retry')


def build_input(report, remote, media_ids):
    payload = report['payload']
    existing = {combination(v['selectedOptions']): v for v in remote['variant_nodes']} if remote else {}
    wanted = {combination(selections(v)) for v in payload['variants']}
    if not set(existing).issubset(wanted):
        raise ShopifyError('variant_removal_requires_explicit_review')
    options = payload['options'] or [{'name': 'Title', 'values': ['Default Title']}]
    result = {'title': payload['title'], 'handle': payload['handle'],
              'descriptionHtml': payload['descriptionHtml'],
              'productOptions': [{'name': option['name'], 'position': index + 1,
                  'values': [{'name': value} for value in option['values']]} for index, option in enumerate(options)],
              'variants': []}
    if not remote:
        result['status'] = 'DRAFT'
        result['metafields'] = [{'namespace': 'teraifoods', 'key': 'django_product_id',
                                'type': 'single_line_text_field', 'value': str(report['product_id'])}]
    # Keep merchant media, including historical detached mappings. No automatic deletion.
    all_ids = list(dict.fromkeys([*media_ids.values(), *([m['id'] for m in remote['media']['nodes']] if remote else [])]))
    alts = {media_ids[image['django_image_id']]: image['alt'] for image in payload['images']
            if image['django_image_id'] in media_ids}
    result['files'] = [({'id': gid, 'alt': alts[gid]} if gid in alts else {'id': gid}) for gid in all_ids]
    for local in payload['variants']:
        values = selections(local)
        row = {'optionValues': [{'optionName': value['name'], 'name': value['value']} for value in values],
               'price': local['price'], 'compareAtPrice': local['compareAtPrice'],
               'inventoryItem': {'tracked': False, 'sku': local['sku'], 'requiresShipping': True,
                   'measurement': {'weight': {'value': float(local['weightGrams']), 'unit': 'GRAMS'}}}}
        previous = existing.get(combination(values))
        if previous:
            row['id'] = previous['id']
        if local.get('django_image_id') in media_ids:
            row['file'] = {'id': media_ids[local['django_image_id']]}
        result['variants'].append(row)
    return result


def verify_result(report, remote, media_ids, *, allow_active=False):
    owned_draft(remote, report['product_id'], allow_active=allow_active)
    if not remote:
        raise ShopifyError('remote_product_missing_after_write')
    expected = report['payload']
    if (remote['title'], remote['handle'], remote['descriptionHtml']) != (
            expected['title'], expected['handle'], expected['descriptionHtml']):
        raise ShopifyError('remote_product_verification_failed')
    actual = {combination(v['selectedOptions']): v for v in remote['variant_nodes']}
    if len(actual) != len(expected['variants']):
        raise ShopifyError('remote_variants_verification_failed')
    for local in expected['variants']:
        item = actual.get(combination(selections(local)))
        if not item or Decimal(item['price']) != Decimal(local['price']) or (item['sku'] or '') != local['sku']:
            raise ShopifyError('remote_variant_verification_failed')
        compare = item['compareAtPrice']
        if (Decimal(compare) if compare is not None else None) != (
                Decimal(local['compareAtPrice']) if local['compareAtPrice'] is not None else None):
            raise ShopifyError('remote_discount_verification_failed')
        inventory = item['inventoryItem']
        if inventory['tracked']:
            raise ShopifyError('inventory_tracking_not_disabled')
        weight = inventory['measurement']['weight']
        factors = {'GRAMS': Decimal(1), 'KILOGRAMS': Decimal(1000),
                   'OUNCES': Decimal('28.349523125'), 'POUNDS': Decimal('453.59237')}
        grams = Decimal(str(weight['value'])) * factors[weight['unit']]
        if abs(grams - Decimal(local['weightGrams'])) > Decimal('.001'):
            raise ShopifyError('remote_weight_verification_failed')
    media = {m['id']: m['status'] for m in remote['media']['nodes']}
    if any(media.get(gid) != 'READY' for gid in media_ids.values()):
        raise ShopifyError('remote_media_not_ready')
    return actual


def _execute(job_id):
    check_enabled()
    # Lock integration rows only. Website catalogue, checkout, stock and payment rows are never locked or changed.
    with transaction.atomic():
        job = ShopifySyncJob.objects.select_for_update().get(pk=job_id)
        if job.operation != 'draft_sync':
            raise ShopifyError('operation_not_supported')
        if job.status not in ('pending', 'retry'):
            return job
        mapping = ShopifyProductMapping.objects.select_for_update(of=('self',)).select_related('connection', 'product').get(pk=job.mapping_id)
        connection = mapping.connection
        report = dry_run(mapping.product, connection)
        if report['errors']:
            raise ShopifyError('local_validation_failed')
        client = ShopifyClient(connection)
        preflight(client)
        job.status, job.claimed_at = 'running', timezone.now()
        job.attempts += 1
        job.save()
        identifier = {'id': mapping.remote_product_gid} if mapping.remote_product_gid else {'handle': report['payload']['handle']}
        remote = snapshot(client, identifier)
        if mapping.remote_product_gid and remote is None:
            raise ShopifyError('mapped_remote_product_missing')
        owned_draft(remote, report['product_id'], allow_active=mapping.publication_approved)
        # Validate the variant diff before any media uploads.
        build_input(report, remote, {})
        images = sorted(report['payload']['images'], key=lambda image: not image['main'])
        media_ids = {image['django_image_id']: ensure_media(client, mapping, image) for image in images}
        data = build_input(report, remote, media_ids)
        if remote:
            identifier = {'id': remote['id']}
        result = client.mutate(PRODUCT_SET, {'input': data, 'identifier': identifier})
        returned = result.get('product')
        if not returned or (returned['status'] != 'DRAFT' and not (mapping.publication_approved and returned['status']=='ACTIVE')):
            raise ShopifyError('invalid_draft_response')
        remote = snapshot(client, {'id': returned['id']})
        actual = verify_result(report, remote, media_ids, allow_active=mapping.publication_approved)
        # Verify that the source/review did not change while the network calls were in flight.
        latest = dry_run(Product.objects.get(pk=mapping.product_id), connection)
        if latest['errors'] or latest['payload_hash'] != report['payload_hash']:
            raise ShopifyError('source_changed_during_sync')
        definitions = {d.key: d for d in mapping.product.channel_variants.all()}
        for local in report['payload']['variants']:
            item = actual[combination(selections(local))]
            ShopifyVariantMapping.objects.update_or_create(product_mapping=mapping, local_key=local['key'], defaults={
                'definition': definitions.get(local['key']), 'remote_variant_gid': item['id'],
                'inventory_item_gid': item['inventoryItem']['id']})
        mapping.remote_product_gid = remote['id']
        mapping.applied_payload, mapping.payload_hash = report['payload'], report['payload_hash']
        mapping.applied_revision, mapping.error_code = job.desired_revision, ''
        mapping.status = ('published' if mapping.status=='published' else 'active_synced') if remote['status']=='ACTIVE' else 'draft_synced'
        mapping.auto_sync = True
        mapping.save()
        job.status, job.error_code, job.next_retry_at = 'succeeded', '', None
        job.save()
        IntegrationLog.objects.create(connection=connection, product_id=mapping.product_id,
                                      operation='draft_sync', status='succeeded')
        return job


def execute_draft(job_id):
    try:
        return _execute(job_id)
    except Exception as exc:
        code = str(exc) if isinstance(exc, ShopifyError) else 'internal_sync_error'
        transient = code in ('transport_error', 'http_429', 'rate_limited', 'http_500', 'http_502',
            'http_503', 'http_504', 'graphql_mutation_error', 'media_processing_retry',
            'source_changed_during_sync', 'remote_media_not_ready')
        transient = transient or code in ('user_error:DUPLICATE_FILENAME', 'user_error:FILE_NAME_ALREADY_EXISTS')
        with transaction.atomic():
            job = ShopifySyncJob.objects.select_for_update().select_related('mapping').get(pk=job_id)
            if job.status == 'succeeded':
                return job
            job.attempts += 1
            job.error_code = code[:60]
            job.status = 'retry' if transient and job.attempts < 5 else 'failed'
            job.next_retry_at = timezone.now() + timedelta(seconds=min(900, 30 * 2 ** job.attempts)) if job.status == 'retry' else None
            job.save()
            ShopifyProductMapping.objects.filter(pk=job.mapping_id).update(status=job.status, error_code=job.error_code)
            IntegrationLog.objects.create(connection_id=job.mapping.connection_id, product_id=job.mapping.product_id,
                operation='draft_sync', status=job.status, codes=[job.error_code])
        logger.warning('Shopify draft job %s: %s', job_id, code)
        return job
