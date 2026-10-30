"""Optional Shopify catalogue integration. Only explicit draft jobs are dispatched."""
import os
from .orders import CELERY_BEAT_SCHEDULE

SHOPIFY_ENABLED = os.getenv('SHOPIFY_ENABLED', 'false').lower() == 'true'
SHOPIFY_SHOP_DOMAIN = os.getenv('SHOPIFY_SHOP_DOMAIN', '').strip()
SHOPIFY_API_VERSION = os.getenv('SHOPIFY_API_VERSION', '2026-10').strip()
SHOPIFY_CLIENT_ID = os.getenv('SHOPIFY_CLIENT_ID', '').strip()
SHOPIFY_CLIENT_SECRET = os.getenv('SHOPIFY_CLIENT_SECRET', '').strip()
# Optional externally provisioned OAuth token; never persisted in integration tables.
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN', '').strip()
SHOPIFY_MEDIA_ORIGIN = os.getenv('SHOPIFY_MEDIA_ORIGIN', '').rstrip('/')
SHOPIFY_HTTP_TIMEOUT = 10
SHOPIFY_MAX_RETRIES = 2
SHOPIFY_DRAFT_SYNC_ENABLED = os.getenv('SHOPIFY_DRAFT_SYNC_ENABLED', 'false').lower() == 'true'
SHOPIFY_PUBLICATION_ENABLED = os.getenv('SHOPIFY_PUBLICATION_ENABLED', 'false').lower() == 'true'
SHOPIFY_ORDER_IMPORT_ENABLED = os.getenv('SHOPIFY_ORDER_IMPORT_ENABLED', 'false').lower() == 'true'
SHOPIFY_AUTO_SYNC_ENABLED = os.getenv('SHOPIFY_AUTO_SYNC_ENABLED', 'false').lower() == 'true'
SHOPIFY_WEBHOOK_PREVIOUS_SECRET = os.getenv('SHOPIFY_WEBHOOK_PREVIOUS_SECRET', '').strip()
SHOPIFY_WEBHOOK_MAX_BYTES = 1024 * 1024
CELERY_BEAT_SCHEDULE['shopify-explicit-draft-jobs'] = {
    'task': 'shopify_integration.tasks.dispatch_draft_jobs', 'schedule': 60.0,
    'options': {'queue': 'shopify'},
}
CELERY_BEAT_SCHEDULE.update({
    'shopify-inbox': {'task': 'shopify_integration.tasks.dispatch_webhooks', 'schedule': 30.0, 'options': {'queue': 'shopify'}},
    'shopify-catalogue-updates': {'task': 'shopify_integration.tasks.sync_managed_products', 'schedule': 120.0, 'options': {'queue': 'shopify'}},
    'shopify-order-reconciliation': {'task': 'shopify_integration.tasks.reconcile_orders', 'schedule': 300.0, 'options': {'queue': 'shopify'}},
    'shopify-retention': {'task': 'shopify_integration.tasks.expire_private_snapshots', 'schedule': 86400.0, 'options': {'queue': 'shopify'}},
})
