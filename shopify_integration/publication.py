"""Explicit, reviewed publication actions, separate from catalogue synchronization."""
import re
import uuid
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from .client import ShopifyClient, ShopifyError
from .graphql import PUBLICATIONS_QUERY, PUBLICATION_STATE, PRODUCT_ACTIVATE, PUBLISH_PRODUCT, UNPUBLISH_PRODUCT, SCOPES_QUERY
from .models import ShopifyProductMapping, ShopifySyncJob, IntegrationLog
from .draft_sync import snapshot, owned_draft, verify_result
from .services import dry_run


def publications(client):
    result = client.query(PUBLICATIONS_QUERY)['publications']
    if result['pageInfo']['hasNextPage']:
        raise ShopifyError('publication_list_requires_pagination_review')
    return result['nodes']


def prepare_publication(connection, product_id, *, operation, reviewed=False, actor=None):
    if not settings.SHOPIFY_PUBLICATION_ENABLED or not connection.enabled:
        raise ShopifyError('publication_disabled')
    if operation not in ('publish','unpublish'):
        raise ShopifyError('invalid_publication_operation')
    if actor is not None and (not actor.is_active or not actor.is_staff or
            not actor.has_perm('shopify_integration.publish_shopify_products')):
        raise PermissionDenied
    ids = connection.publication_ids
    if not isinstance(ids,list) or not ids or any(
            not isinstance(gid,str) or not re.fullmatch(r'gid://shopify/Publication/[0-9]+',gid) for gid in ids) or len(set(ids))!=len(ids):
        raise ShopifyError('choose_valid_publication_ids_first')
    with transaction.atomic():
        mapping = ShopifyProductMapping.objects.select_for_update(of=('self',)).select_related('product').filter(connection=connection, product_id=product_id).first()
        if not mapping or not mapping.remote_product_gid:
            raise ShopifyError('synchronize_product_before_publication')
        report = dry_run(mapping.product, connection)
        if operation=='publish' and (not reviewed or report['errors'] or report['payload_hash']!=mapping.payload_hash):
            raise ShopifyError('current_product_review_and_sync_required')
        return ShopifySyncJob.objects.create(mapping=mapping, operation=operation, actor=actor,
            desired_revision=mapping.applied_revision, idempotency_key=uuid.uuid4().hex,
            parameters={'publication_ids':ids, 'reviewed_hash':report['payload_hash'] if operation=='publish' else None})


def execute_publication(job_id):
    try:
        with transaction.atomic():
            job = ShopifySyncJob.objects.select_for_update().get(pk=job_id)
            if job.status=='succeeded':
                return job
            if job.operation not in ('publish','unpublish') or not settings.SHOPIFY_PUBLICATION_ENABLED:
                raise ShopifyError('publication_disabled')
            if job.actor_id and (not job.actor.is_active or not job.actor.is_staff or
                    not job.actor.has_perm('shopify_integration.publish_shopify_products')):
                raise ShopifyError('publication_permission_revoked')
            mapping = ShopifyProductMapping.objects.select_for_update(of=('self',)).select_related('product','connection').get(pk=job.mapping_id)
            client = ShopifyClient(mapping.connection)
            scopes = {s['handle'] for s in client.query(SCOPES_QUERY)['currentAppInstallation']['accessScopes']}
            if not {'write_products','write_publications'}.issubset(scopes):
                raise ShopifyError('missing_publication_scopes')
            targets = job.parameters.get('publication_ids',[])
            allowed = {p['id'] for p in publications(client)}
            if not targets or not set(targets).issubset(allowed) or not set(targets).issubset(mapping.connection.publication_ids):
                raise ShopifyError('publication_target_not_approved')
            remote = snapshot(client, {'id':mapping.remote_product_gid})
            if not remote:
                raise ShopifyError('remote_product_missing')
            owned_draft(remote, mapping.product_id, allow_active=True)
            if job.operation=='publish':
                report = dry_run(mapping.product, mapping.connection)
                if report['errors'] or report['payload_hash']!=job.parameters.get('reviewed_hash') or report['payload_hash']!=mapping.payload_hash:
                    raise ShopifyError('product_changed_after_publication_review')
                files = {m.image_id:m.remote_file_gid for m in mapping.shopifymediamapping_set.filter(image__isnull=False,status='ready')}
                verify_result(report,remote,files,allow_active=True)
                if remote['status']=='DRAFT':
                    client.mutate(PRODUCT_ACTIVATE,{'product':{'id':remote['id'],'status':'ACTIVE'}})
                client.mutate(PUBLISH_PRODUCT,{'id':remote['id'],'input':[{'publicationId':gid} for gid in targets]})
            else:
                client.mutate(UNPUBLISH_PRODUCT,{'id':remote['id'],'input':[{'publicationId':gid} for gid in targets]})
            for gid in targets:
                state = client.query(PUBLICATION_STATE,{'id':remote['id'],'publication':gid})['product']
                if not state or state['publishedOnPublication'] != (job.operation=='publish'):
                    raise ShopifyError('publication_verification_failed')
            if job.operation=='publish':
                mapping.publication_approved = True
            mapping.status = 'published' if job.operation=='publish' else 'unpublished'
            mapping.error_code = ''
            mapping.save(update_fields=['publication_approved','status','error_code','updated_at'])
            job.status,job.error_code = 'succeeded',''
            job.attempts += 1
            job.save()
            IntegrationLog.objects.create(connection=mapping.connection,product=mapping.product,
                operation=job.operation,status='succeeded')
            return job
    except Exception as exc:
        code = str(exc)[:60] if isinstance(exc,ShopifyError) else 'publication_action_failed'
        # No automatic retry or compensating unpublish/archive/delete. Retry is an explicit staff action.
        ShopifySyncJob.objects.filter(pk=job_id).update(status='failed',error_code=code)
        job = ShopifySyncJob.objects.select_related('mapping').get(pk=job_id)
        IntegrationLog.objects.create(connection_id=job.mapping.connection_id,product_id=job.mapping.product_id,
            operation=job.operation,status='failed',codes=[code])
        return job
