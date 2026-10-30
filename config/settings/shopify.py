"""Optional Shopify foundation. No automatic jobs or publishing are registered."""
import os

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
