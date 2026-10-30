"""Shopify financial authority, isolated from website checkout, payments and inventory."""
import base64
from datetime import timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import re

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from catalog.models import Order, OrderLine
from orders.services import emit
from .client import ShopifyClient, ShopifyError
from .graphql import ORDER_QUERY, ORDERS_QUERY
from .models import ShopifyOrderMapping, ShopifyOrderLineMapping, ShopifyVariantMapping


def cipher():
    key = hmac.new(settings.SECRET_KEY.encode(), b'teraifoods-shopify-snapshots-v1', hashlib.sha256).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def imports_enabled(connection):
    return (settings.SHOPIFY_ENABLED and settings.SHOPIFY_ORDER_IMPORT_ENABLED and connection.enabled
            and connection.import_orders_enabled and connection.shop_domain==settings.SHOPIFY_SHOP_DOMAIN)


def order_gid(value):
    if isinstance(value, str) and re.fullmatch(r'gid://shopify/Order/[0-9]+', value):
        return value
    raise ShopifyError('invalid_order_id')


def money(data, *, max_digits=14):
    try:
        shop = data['shopMoney']
        if shop['currencyCode'] != 'GBP':
            raise ShopifyError('order_currency_mismatch')
        value = Decimal(shop['amount'])
        if not value.is_finite() or value < 0 or value != value.quantize(Decimal('.01')) or value >= Decimal(10) ** (max_digits-2):
            raise ShopifyError('invalid_order_money')
        return value
    except (KeyError, TypeError, InvalidOperation, ValueError):
        raise ShopifyError('invalid_order_money') from None


def address(data):
    data = data or {}
    return {key: data.get(source) or '' for key, source in {
        'name': 'name', 'phone': 'phone', 'line1': 'address1', 'line2': 'address2',
        'city': 'city', 'county': 'province', 'postcode': 'zip', 'country': 'countryCodeV2'}.items()}


def fetch_order(client, gid):
    nodes, after, version = [], None, None
    for _ in range(100):
        data = client.query(ORDER_QUERY, {'id': order_gid(gid), 'after': after})['order']
        if data is None:
            raise ShopifyError('remote_order_missing_or_inaccessible')
        if version is not None and data['updatedAt']!=version:
            raise ShopifyError('order_changed_during_fetch')
        version = data['updatedAt']
        nodes.extend(data['lineItems']['nodes'])
        page = data['lineItems']['pageInfo']
        if not page['hasNextPage']:
            data['lineItems']['nodes'] = nodes
            return data
        if not page['endCursor'] or page['endCursor'] == after:
            break
        after = page['endCursor']
    raise ShopifyError('order_line_pagination_incomplete')


def _import(connection, data):
    gid = order_gid(data['id'])
    updated = parse_datetime(data.get('updatedAt', ''))
    created = parse_datetime(data.get('createdAt', ''))
    if not updated or not created or timezone.is_naive(updated) or timezone.is_naive(created):
        raise ShopifyError('invalid_order_timestamp')
    if data.get('currencyCode') != 'GBP':
        raise ShopifyError('order_currency_mismatch')
    with transaction.atomic():
        mapping, _ = ShopifyOrderMapping.objects.get_or_create(connection=connection, remote_order_gid=gid)
        mapping = ShopifyOrderMapping.objects.select_for_update().get(pk=mapping.pk)
        if mapping.order_id and mapping.remote_updated_at and updated <= mapping.remote_updated_at:
            return mapping
        lines = data['lineItems']['nodes']
        if not isinstance(lines, list) or not lines or data['lineItems']['pageInfo']['hasNextPage']:
            raise ShopifyError('incomplete_order_lines')
        identifiers = [line['id'] for line in lines]
        if len(set(identifiers)) != len(identifiers):
            raise ShopifyError('duplicate_remote_order_line')
        resolved = []
        for line in lines:
            variant_id = (line.get('variant') or {}).get('id')
            variant = ShopifyVariantMapping.objects.select_related('product_mapping__product').filter(
                product_mapping__connection=connection, remote_variant_gid=variant_id).first() if variant_id else None
            if variant is None and mapping.order_id:
                previous = ShopifyOrderLineMapping.objects.select_related('variant_mapping__product_mapping__product').filter(
                    order_mapping=mapping, remote_line_gid=line['id']).first()
                variant = previous.variant_mapping if previous else None
            if variant is None:
                raise ShopifyError('unmapped_shopify_variant')
            product = variant.product_mapping.product
            if product.is_package:
                raise ShopifyError('package_order_requires_review')
            quantity = line.get('currentQuantity')
            if type(quantity) is not int or not 0 <= quantity <= 2147483647:
                raise ShopifyError('invalid_order_quantity')
            price = money(line['originalUnitPriceSet'], max_digits=12)
            if len(line['id']) > 255:
                raise ShopifyError('invalid_order_line_id')
            resolved.append((line, variant, product, quantity, price))
        totals = {key: money(data[source], max_digits=digits) for key, source, digits in (
            ('total', 'currentTotalPriceSet', 14), ('subtotal', 'currentSubtotalPriceSet', 14),
            ('tax', 'currentTotalTaxSet', 12), ('discount', 'currentTotalDiscountsSet', 12),
            ('delivery_charge', 'currentShippingPriceSet', 10))}
        financial_status = data.get('displayFinancialStatus')
        if financial_status not in ('PAID','PARTIALLY_REFUNDED','REFUNDED','PENDING','AUTHORIZED','PARTIALLY_PAID','VOIDED','EXPIRED'):
            raise ShopifyError('unsupported_order_payment_status')
        payment_status = ('paid' if financial_status in ('PAID', 'PARTIALLY_REFUNDED') else
                          'refunded' if financial_status == 'REFUNDED' else
                          'failed' if financial_status in ('VOIDED', 'EXPIRED') else 'pending')
        order = Order.objects.select_for_update().get(pk=mapping.order_id) if mapping.order_id else None
        if order and order.sales_channel != 'shopify':
            raise ShopifyError('order_channel_mismatch')
        if order is None:
            identity = hashlib.sha256((connection.shop_domain + ':' + gid).encode()).hexdigest()
            order = Order(sales_channel='shopify', payment_method='shopify', customer=None,
                idempotency_key='shopify:' + identity, request_digest=identity, currency='GBP',
                reservation_expires_at=None, fulfilment_status='placed' if payment_status=='paid' else 'pending_payment')
        shipping = address(data.get('shippingAddress'))
        order.email = (data.get('email') or '')[:254]
        order.recipient_name = shipping['name'][:150]
        order.phone = (data.get('phone') or shipping['phone'])[:30]
        order.address, order.billing_address = shipping, address(data.get('billingAddress'))
        for key, value in totals.items():
            setattr(order, key, value)
        order.payment_status = payment_status
        order.refund_status = 'refunded' if financial_status=='REFUNDED' else 'partially_refunded' if financial_status=='PARTIALLY_REFUNDED' else 'none'
        if data.get('cancelledAt'):
            order.status, order.fulfilment_status, order.cancellation_status = 'cancelled', 'cancelled', 'cancelled'
        elif order.fulfilment_status == 'pending_payment' and payment_status == 'paid':
            order.fulfilment_status = 'placed'
        if data.get('displayFulfillmentStatus') == 'FULFILLED' and not data.get('cancelledAt') and order.fulfilment_status not in ('delivered','out_for_delivery'):
            order.fulfilment_status = 'dispatched'
        order.save()
        Order.objects.filter(pk=order.pk).update(created_at=created)
        order.created_at = created
        mapping.order = order
        retained_ids = []
        for line, variant, product, quantity, price in resolved:
            link, _ = ShopifyOrderLineMapping.objects.get_or_create(order_mapping=mapping, remote_line_gid=line['id'])
            local = link.line if link.line_id else OrderLine(order=order, product=product)
            local.product = product
            local.quantity, local.unit_price = quantity, price
            local.product_name = ((line.get('name') or product.name) +
                (' — ' + line['variantTitle'] if line.get('variantTitle') and line['variantTitle']!='Default Title' else ''))[:300]
            local.product_sku = (line.get('sku') or '')[:80]
            local.product_image = product.image_url
            local.unit_weight_grams = product.weight_grams
            weight = ((((line.get('variant') or {}).get('inventoryItem') or {}).get('measurement') or {}).get('weight'))
            if weight:
                factors = {'GRAMS':Decimal(1),'KILOGRAMS':Decimal(1000),'POUNDS':Decimal('453.59237'),'OUNCES':Decimal('28.349523125')}
                value = Decimal(str(weight['value']))*factors[weight['unit']]
                if not value.is_finite() or value<0 or value>=Decimal('10000000000'):
                    raise ShopifyError('invalid_order_weight')
                local.unit_weight_grams=value.quantize(Decimal('.001'))
            local.save()
            link.line, link.variant_mapping = local, variant
            link.snapshot = {'quantity': line.get('quantity'), 'current_quantity': quantity,
                'original_unit_price': line['originalUnitPriceSet'], 'variant_title': line.get('variantTitle')}
            link.save()
            retained_ids.append(link.pk)
        # Retain historical lines and their foreign keys after edits; never restore inventory.
        removed = mapping.shopifyorderlinemapping_set.exclude(pk__in=retained_ids)
        OrderLine.objects.filter(pk__in=removed.values('line_id')).update(quantity=0)
        mapping.remote_order_name = (data.get('name') or '')[:100]
        mapping.remote_updated_at, mapping.imported_at = updated, timezone.now()
        mapping.snapshot_saved_at = timezone.now()
        mapping.financial_snapshot = {key: data.get(key) for key in (
            'currencyCode', 'taxesIncluded', 'displayFinancialStatus', 'displayFulfillmentStatus',
            'currentTotalPriceSet', 'currentSubtotalPriceSet', 'currentTotalDiscountsSet',
            'currentTotalTaxSet', 'currentShippingPriceSet', 'totalRefundedSet',
            'currentTotalDutiesSet', 'currentTotalAdditionalFeesSet','totalTipReceivedSet')}
        mapping.payload_encrypted = cipher().encrypt(json.dumps(data).encode()).decode()
        mapping.status, mapping.error_code = 'imported', ''
        mapping.save()
        emit(order, 'shopify_updated', 'Shopify order synchronized; payments remain managed in Shopify.')
        return mapping


def import_snapshot(connection, data, *, allow_historical=False):
    connection.refresh_from_db(fields=['enabled','import_orders_enabled','import_started_at'])
    if not imports_enabled(connection):
        raise ShopifyError('order_import_disabled')
    gid = order_gid(data.get('id'))
    created_value = data.get('createdAt')
    created = parse_datetime(created_value) if isinstance(created_value,str) else None
    if (not allow_historical and connection.import_started_at and created and not timezone.is_naive(created)
            and created<connection.import_started_at and not ShopifyOrderMapping.objects.filter(connection=connection,
                remote_order_gid=gid,order__isnull=False).exists()):
        mapping,_=ShopifyOrderMapping.objects.get_or_create(connection=connection,remote_order_gid=gid,
            defaults={'status':'ignored','error_code':'historical_import_not_enabled'})
        return mapping
    try:
        return _import(connection, data)
    except Exception as exc:
        code = str(exc)[:60] if isinstance(exc, ShopifyError) else 'invalid_order_snapshot'
        with transaction.atomic():
            mapping, _ = ShopifyOrderMapping.objects.get_or_create(connection=connection, remote_order_gid=gid)
            mapping = ShopifyOrderMapping.objects.select_for_update().get(pk=mapping.pk)
            mapping.payload_encrypted = cipher().encrypt(json.dumps(data).encode()).decode()
            mapping.snapshot_saved_at = timezone.now()
            mapping.status, mapping.error_code = 'quarantined', code
            mapping.save()
        return mapping


def import_order(connection, gid, *, allow_historical=False):
    if not imports_enabled(connection):
        raise ShopifyError('order_import_disabled')
    return import_snapshot(connection, fetch_order(ShopifyClient(connection), gid),allow_historical=allow_historical)


def reconcile(connection):
    if not imports_enabled(connection):
        return 0
    now = timezone.now()
    # One durable page per run. Overlap catches boundary updates; imported order IDs deduplicate.
    end = connection.order_sync_window_end or now
    start = connection.order_sync_cursor or now
    query = f'updated_at:>={(start-timedelta(minutes=10)).isoformat()} updated_at:<={end.isoformat()}'
    if connection.import_started_at:
        query += f' created_at:>={connection.import_started_at.isoformat()}'
    api = ShopifyClient(connection)
    page = api.query(ORDERS_QUERY, {'query': query, 'after': connection.order_sync_after})['orders']
    for item in page['nodes']:
        import_snapshot(connection, fetch_order(api, item['id']))
    if page['pageInfo']['hasNextPage']:
        connection.order_sync_after = page['pageInfo']['endCursor']
        connection.order_sync_window_end = end
    else:
        connection.order_sync_cursor, connection.order_sync_after, connection.order_sync_window_end = end, '', None
    connection.save(update_fields=['order_sync_cursor','order_sync_after','order_sync_window_end'])
    return len(page['nodes'])
