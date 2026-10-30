"""Allowlisted GraphQL client. Draft catalogue writes require a separate enable flag."""
import json
import logging
import random
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from .graphql import SCOPES_QUERY, FILES_QUERY, FILE_QUERY, PRODUCT_SNAPSHOT, FILE_CREATE, PRODUCT_SET
from .graphql import (PUBLICATIONS_QUERY, PUBLICATION_STATE, PRODUCT_ACTIVATE, PUBLISH_PRODUCT,
    UNPUBLISH_PRODUCT, WEBHOOKS_QUERY, WEBHOOK_CREATE, ORDER_QUERY, ORDERS_QUERY)

logger = logging.getLogger(__name__)
SHOP_QUERY = 'query IntegrationShop { shop { id name currencyCode } }'
PRODUCT_QUERY = 'query IntegrationProduct($id: ID!) { product(id: $id) { id title status } }'
READ_QUERIES = frozenset((SHOP_QUERY, PRODUCT_QUERY, SCOPES_QUERY, FILES_QUERY, FILE_QUERY, PRODUCT_SNAPSHOT,
    PUBLICATIONS_QUERY, PUBLICATION_STATE, WEBHOOKS_QUERY, ORDER_QUERY, ORDERS_QUERY))


class ShopifyError(Exception):
    """Safe error code only; provider bodies can contain secrets or personal data."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_domain(domain):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*\.myshopify\.com', domain or ''):
        raise ImproperlyConfigured('SHOPIFY_SHOP_DOMAIN must be a canonical myshopify.com hostname.')
    return domain


class ShopifyClient:
    def __init__(self, connection):
        if not settings.SHOPIFY_ENABLED or not connection.enabled:
            raise ImproperlyConfigured('Shopify read access is disabled.')
        self.domain = validate_domain(connection.shop_domain)
        if self.domain != settings.SHOPIFY_SHOP_DOMAIN:
            raise ImproperlyConfigured('Shopify connection does not match configured credential domain.')
        self.version = connection.api_version
        if not re.fullmatch(r'\d{4}-(01|04|07|10)', self.version) or self.version != settings.SHOPIFY_API_VERSION:
            raise ImproperlyConfigured('Shopify API version does not match configuration.')
        self._token = None
        self._expires_at = 0
        self._opener = build_opener(NoRedirect())

    def _post(self, path, body, headers, *, retry=True):
        request = Request(f'https://{self.domain}{path}', data=body,
                          headers={**headers, 'Accept': 'application/json'}, method='POST')
        max_retries = settings.SHOPIFY_MAX_RETRIES if retry else 0
        for attempt in range(max_retries + 1):
            retry_after = None
            try:
                with self._opener.open(request, timeout=settings.SHOPIFY_HTTP_TIMEOUT) as response:
                    data = json.loads(response.read(4 * 1024 * 1024))
                    if not isinstance(data, dict):
                        raise ShopifyError('invalid_response')
                    return data
            except HTTPError as exc:
                retryable = exc.code == 429 or exc.code in (500, 502, 503, 504)
                code = 'rate_limited' if exc.code == 429 else f'http_{exc.code}'
                try:
                    retry_after = min(30, max(0, float(exc.headers.get('Retry-After', '0'))))
                except (TypeError, ValueError):
                    pass
                exc.close()
            except (URLError, TimeoutError, OSError):
                retryable, code = True, 'transport_error'
            except (ValueError, UnicodeError):
                raise ShopifyError('invalid_response') from None
            if not retryable or attempt == max_retries:
                logger.warning('Shopify request failed: %s', code)
                raise ShopifyError(code) from None
            time.sleep(max(retry_after or 0, 2 ** attempt + random.random()))
        raise ShopifyError('transport_error')

    def access_token(self):
        if settings.SHOPIFY_ACCESS_TOKEN:
            return settings.SHOPIFY_ACCESS_TOKEN
        if self._token and time.monotonic() < self._expires_at:
            return self._token
        if not settings.SHOPIFY_CLIENT_ID or not settings.SHOPIFY_CLIENT_SECRET:
            raise ImproperlyConfigured('Shopify credentials are not configured.')
        result = self._post('/admin/oauth/access_token', urlencode({
            'grant_type': 'client_credentials', 'client_id': settings.SHOPIFY_CLIENT_ID,
            'client_secret': settings.SHOPIFY_CLIENT_SECRET,
        }).encode(), {'Content-Type': 'application/x-www-form-urlencoded'})
        token, expires = result.get('access_token'), result.get('expires_in')
        if not isinstance(token, str) or not token or type(expires) is not int or expires <= 60:
            raise ShopifyError('invalid_token_response')
        self._token, self._expires_at = token, time.monotonic() + expires - 60
        return token

    def query(self, document, variables=None):
        # An allowlist, rather than a keyword check, also rejects mixed query/mutation documents.
        if document not in READ_QUERIES:
            raise ShopifyError('operation_not_allowed_in_phase_1')
        headers = {'Content-Type': 'application/json', 'X-Shopify-Access-Token': self.access_token()}
        body = json.dumps({'query': document, 'variables': variables or {}}).encode()
        for attempt in range(settings.SHOPIFY_MAX_RETRIES + 1):
            result = self._post(f'/admin/api/{self.version}/graphql.json', body, headers)
            errors = result.get('errors')
            if errors:
                throttled = isinstance(errors, list) and all(
                    isinstance(e, dict) and isinstance(e.get('extensions'), dict)
                    and e['extensions'].get('code') == 'THROTTLED' for e in errors)
                if throttled and attempt < settings.SHOPIFY_MAX_RETRIES:
                    time.sleep(2 ** attempt + random.random())
                    continue
                raise ShopifyError('graphql_throttled' if throttled else 'graphql_error')
            if not isinstance(result.get('data'), dict):
                raise ShopifyError('invalid_response')
            return result['data']

    def mutate(self, document, variables=None):
        publication = document in (PRODUCT_ACTIVATE, PUBLISH_PRODUCT, UNPUBLISH_PRODUCT)
        webhook = document == WEBHOOK_CREATE
        if publication and not settings.SHOPIFY_PUBLICATION_ENABLED:
            raise ShopifyError('publication_disabled')
        if not publication and not webhook and not settings.SHOPIFY_DRAFT_SYNC_ENABLED:
            raise ShopifyError('draft_sync_disabled')
        if document not in (FILE_CREATE, PRODUCT_SET, PRODUCT_ACTIVATE, PUBLISH_PRODUCT, UNPUBLISH_PRODUCT, WEBHOOK_CREATE):
            raise ShopifyError('mutation_not_allowed')
        if document == PRODUCT_ACTIVATE and (variables or {}).get('product', {}).get('status') != 'ACTIVE':
            raise ShopifyError('invalid_activation')
        if document == PRODUCT_SET:
            data = (variables or {}).get('input', {})
            # Active/archived transitions and publication are never accepted here.
            if 'status' in data and data['status'] != 'DRAFT':
                raise ShopifyError('publication_not_allowed')
        result = self._post(f'/admin/api/{self.version}/graphql.json',
            json.dumps({'query': document, 'variables': variables or {}}).encode(),
            {'Content-Type': 'application/json', 'X-Shopify-Access-Token': self.access_token()}, retry=False)
        # An uncertain mutation is not replayed here. The job reconciles stable identities first.
        if result.get('errors'):
            raise ShopifyError('graphql_mutation_error')
        data = result.get('data')
        key = {FILE_CREATE: 'fileCreate', PRODUCT_SET: 'productSet', PRODUCT_ACTIVATE: 'productUpdate',
            PUBLISH_PRODUCT: 'publishablePublish', UNPUBLISH_PRODUCT: 'publishableUnpublish',
            WEBHOOK_CREATE: 'webhookSubscriptionCreate'}[document]
        if not isinstance(data, dict) or not isinstance(data.get(key), dict):
            raise ShopifyError('invalid_mutation_response')
        errors = data[key].get('userErrors')
        if errors:
            codes = {e.get('code') for e in errors if isinstance(e, dict)}
            safe = sorted(c for c in codes if isinstance(c, str) and re.fullmatch(r'[A-Z_]{1,50}', c))
            raise ShopifyError('user_error:' + ','.join(safe or ['UNKNOWN']))
        return data[key]
