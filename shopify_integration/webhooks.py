import base64
from datetime import timedelta
import hashlib
import hmac
import json
import logging
import re

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import ShopifyConnection, ShopifyWebhookReceipt
from .order_import import import_order, imports_enabled

logger = logging.getLogger(__name__)
TOPICS = ('orders/create','orders/updated','orders/paid','orders/cancelled','refunds/create','app/uninstalled')


def valid_hmac(body, signature):
    try:
        supplied = base64.b64decode(signature, validate=True)
    except (ValueError, TypeError):
        return False
    secrets = (settings.SHOPIFY_CLIENT_SECRET, settings.SHOPIFY_WEBHOOK_PREVIOUS_SECRET)
    return any(secret and hmac.compare_digest(hmac.new(secret.encode(), body, hashlib.sha256).digest(), supplied) for secret in secrets)


@csrf_exempt
@require_POST
def receive(request):
    if not settings.SHOPIFY_ENABLED or not settings.SHOPIFY_CLIENT_SECRET:
        return JsonResponse({'error': 'webhook_not_configured'}, status=503)
    try:
        if int(request.META.get('CONTENT_LENGTH') or 0) > settings.SHOPIFY_WEBHOOK_MAX_BYTES:
            return JsonResponse({'error': 'payload_too_large'}, status=413)
        body = request.body
    except RequestDataTooBig:
        return JsonResponse({'error': 'payload_too_large'}, status=413)
    except ValueError:
        return JsonResponse({'error': 'invalid_length'}, status=400)
    if len(body) > settings.SHOPIFY_WEBHOOK_MAX_BYTES:
        return JsonResponse({'error': 'payload_too_large'}, status=413)
    if not valid_hmac(body, request.headers.get('X-Shopify-Hmac-Sha256', '')):
        return JsonResponse({'error': 'invalid_signature'}, status=401)
    domain = request.headers.get('X-Shopify-Shop-Domain', '').lower()
    topic = request.headers.get('X-Shopify-Topic', '')
    delivery = request.headers.get('X-Shopify-Webhook-Id', '')
    if domain != settings.SHOPIFY_SHOP_DOMAIN or topic not in TOPICS or not delivery or len(delivery)>255:
        return JsonResponse({'error': 'invalid_webhook_headers'}, status=400)
    connection = ShopifyConnection.objects.filter(shop_domain=domain).first()
    if not connection or (not connection.enabled and topic!='app/uninstalled'):
        return JsonResponse({'error': 'connection_disabled'}, status=403)
    try:
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError
        envelope = {}
        if topic == 'app/uninstalled':
            if data.get('myshopify_domain') != domain:
                raise ValueError
        else:
            identifier = data.get('order_id') if topic=='refunds/create' else data.get('id')
            if type(identifier) not in (int, str) or not re.fullmatch('[0-9]+', str(identifier)):
                raise ValueError
            envelope['order_gid'] = 'gid://shopify/Order/' + str(identifier)
    except (ValueError, TypeError, UnicodeError):
        return JsonResponse({'error': 'invalid_payload'}, status=400)
    digest = hashlib.sha256(body).hexdigest()
    with transaction.atomic():
        receipt, created = ShopifyWebhookReceipt.objects.get_or_create(connection=connection, delivery_id=delivery,
            defaults={'topic':topic, 'event_id':request.headers.get('X-Shopify-Event-Id','')[:255],
                      'payload':envelope, 'body_sha256':digest})
        if not created and (receipt.body_sha256 != digest or receipt.topic != topic):
            return JsonResponse({'error': 'delivery_conflict'}, status=409)
        if topic == 'app/uninstalled':
            connection.enabled, connection.import_orders_enabled = False, False
            connection.save(update_fields=['enabled','import_orders_enabled'])
            receipt.status, receipt.processed_at = 'processed', timezone.now()
            receipt.save(update_fields=['status','processed_at'])
        elif created and imports_enabled(connection):
            def enqueue():
                try:
                    from .tasks import process_webhook
                    process_webhook.apply_async(args=[receipt.pk], queue='shopify')
                except Exception:
                    logger.warning('Shopify receipt persisted; broker unavailable.')
            transaction.on_commit(enqueue)
    return JsonResponse({'received':True})


def process_receipt(pk):
    from .client import ShopifyError
    with transaction.atomic():
        receipt = ShopifyWebhookReceipt.objects.select_for_update(of=('self',)).select_related('connection').get(pk=pk)
        if receipt.status in ('processed','quarantined') or not imports_enabled(receipt.connection):
            return receipt
        try:
            mapping = import_order(receipt.connection, receipt.payload['order_gid'])
        except Exception as exc:
            code = str(exc)[:60] if isinstance(exc, ShopifyError) else 'order_import_unavailable'
            receipt.attempts += 1
            receipt.status = 'retry' if receipt.attempts<8 else 'failed'
            receipt.error_code = code
            receipt.next_retry_at = timezone.now()+timedelta(seconds=min(3600,30*2**receipt.attempts))
        else:
            receipt.attempts += 1
            receipt.status = 'processed' if mapping.status in ('imported','ignored') else 'quarantined'
            receipt.error_code = mapping.error_code
            receipt.processed_at = timezone.now()
        receipt.save()
        return receipt
