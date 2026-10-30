"""Pure local catalogue projection; no client, writes or source metadata mutations."""
import hashlib
import ipaddress
import json
from decimal import Decimal, InvalidOperation
from html import escape
from urllib.parse import urljoin, urlsplit

from django.conf import settings

MANAGED_FIELDS = ('title', 'handle', 'descriptionHtml', 'options', 'variants', 'images')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def variant_fingerprint(product, definitions):
    metadata = product.metadata if isinstance(product.metadata, dict) else {}
    return digest({'product': [product.pk, product.regular_price, product.sale_price, product.weight, product.weight_unit,
                              product.sku if any(not d.sku for d in definitions) else None],
                   'source_options': metadata.get('source_options'), 'source_variants': metadata.get('source_variants'),
                   'definitions': [{'key': d.key, 'source_variant_id': d.source_variant_id, 'options': d.option_values,
                                    'policy': d.price_policy, 'price': d.price, 'compare': d.compare_at_price,
                                    'sku': d.sku, 'weight': d.weight_grams, 'image': d.image_id} for d in definitions]})


def public_image_url(value):
    if not isinstance(value, str) or not value or '\\' in value:
        return None
    origin = settings.SHOPIFY_MEDIA_ORIGIN
    if value.startswith('/') and not value.startswith('//') and origin:
        value = urljoin(origin + '/', value)
    try:
        parsed = urlsplit(value)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
            return None
        if parsed.hostname.lower() in ('localhost', 'testserver') or '.' not in parsed.hostname:
            return None
        try:
            if not ipaddress.ip_address(parsed.hostname).is_global:
                return None
        except ValueError:
            pass
        return value if not parsed.fragment else None
    except ValueError:
        return None


def money(value, errors, code, *, optional=False):
    if value is None and optional:
        return None
    try:
        number = Decimal(str(value))
        if not number.is_finite() or not 0 < number <= Decimal('9999999999.99') or number != number.quantize(Decimal('.01')):
            raise ValueError
        return format(number, '.2f')
    except (InvalidOperation, ValueError, TypeError):
        errors.append(code)
        return None


def normalize_product(product, *, require_review=True):
    from .models import VariantReview

    errors = []
    metadata = product.metadata if isinstance(product.metadata, dict) else {}
    if not isinstance(product.metadata, dict):
        errors.append('invalid_source_metadata')
    definitions = list(product.channel_variants.order_by('key'))
    review = VariantReview.objects.filter(product=product).first()
    source_variants = metadata.get('source_variants', [])
    source_options = metadata.get('source_options', [])
    source_variants = [] if source_variants is None else source_variants
    source_options = [] if source_options is None else source_options
    if not isinstance(source_variants, list):
        errors.append('invalid_source_variants')
        source_variants = []
    if not isinstance(source_options, list):
        errors.append('invalid_source_options')
    # Validate entries before classifying a lone record as a simple default variant.
    for entry in source_variants:
        if not isinstance(entry, dict):
            errors.append('invalid_source_variants')
            continue
        identifier = entry.get('id')
        selections = entry.get('optionsSelections', [])
        if (not isinstance(identifier, str) or not identifier.strip()
                or not isinstance(selections, list)
                or any(type(value) not in (str, int) or value == '' for value in selections)):
            errors.append('invalid_source_variants')
    has_source_options = bool(metadata.get('source_options') or len(source_variants) > 1 or any(
        isinstance(v, dict) and v.get('optionsSelections') for v in source_variants))
    # An options-bearing product is never silently downgraded to a default variant.
    is_variant = has_source_options or bool(definitions) or review is not None
    if not product.name.strip():
        errors.append('missing_name')
    if len(product.name) > 255:
        errors.append('shopify_title_too_long')
    if not product.is_active or not product.is_published or product.is_archived:
        errors.append('product_not_public')
    if not product.category_id or not product.category.is_active:
        errors.append('inactive_or_missing_category')
    if product.subcategory_id and (not product.subcategory.is_active or product.subcategory.category_id != product.category_id):
        errors.append('invalid_subcategory')
    if product.is_package:
        errors.append('packages_not_supported_in_phase_1')
    if metadata.get('source_currency', 'GBP') != 'GBP':
        errors.append('unreviewed_currency')
    images = []
    for image in product.images.all():
        url = public_image_url(image.url)
        # The website may serve AVIF. Use its retained Django JPEG rendition for Shopify ingestion.
        renditions = image.variants.get('jpeg', {}) if isinstance(image.variants, dict) else {}
        widths = [key for key in renditions if str(key).isdigit()] if isinstance(renditions, dict) else []
        if widths:
            from catalog.media import media_url
            url = public_image_url(media_url(renditions[max(widths, key=int)]))
        images.append({'django_image_id': image.pk, 'url': url, 'alt': image.alt,
                       'digest': image.digest, 'main': image.is_main})
        if not url:
            errors.append('image_requires_public_https_url')
    if not images or not any(i['main'] for i in images):
        errors.append('missing_main_image')
    variants, option_names, combinations = [], [], set()
    if is_variant and not definitions:
        errors.append('normalized_variants_required')
    if len(definitions) > 2048:
        errors.append('variant_limit_exceeded')
    if is_variant and source_variants:
        source_ids = [str(v.get('id') or '') for v in source_variants if isinstance(v, dict)]
        mapped_ids = [d.source_variant_id for d in definitions]
        if (len(source_ids) != len(source_variants) or not all(source_ids)
                or len(set(source_ids)) != len(source_ids) or sorted(source_ids) != sorted(mapped_ids)):
            errors.append('incomplete_source_variant_mapping')
    if is_variant and require_review:
        if not review or review.fingerprint != variant_fingerprint(product, definitions):
            errors.append('variant_review_required_or_stale')
    for definition in definitions:
        if not definition.key or definition.key.strip() != definition.key:
            errors.append('invalid_variant_key')
        selections = definition.option_values
        valid = isinstance(selections, list) and 1 <= len(selections) <= 3 and all(
            isinstance(s, dict) and set(s) == {'name', 'value'} and
            all(isinstance(s[k], str) and s[k].strip() == s[k] and 0 < len(s[k]) <= 255 for k in ('name', 'value'))
            for s in selections)
        if not valid:
            errors.append('invalid_option_mapping')
            continue
        names = [s['name'] for s in selections]
        if len(set(names)) != len(names) or (option_names and names != option_names):
            errors.append('inconsistent_option_names')
        option_names = option_names or names
        combination = tuple((s['name'], s['value']) for s in selections)
        if combination in combinations:
            errors.append('duplicate_option_combination')
        combinations.add(combination)
        if definition.price_policy == 'inherit':
            if definition.price is not None or definition.compare_at_price is not None:
                errors.append('ambiguous_inherited_price')
            price, compare = product.sale_price or product.regular_price, product.regular_price if product.sale_price else None
        elif definition.price_policy == 'explicit':
            price, compare = definition.price, definition.compare_at_price
        else:
            errors.append('unresolved_price_policy')
            price, compare = None, None
        price = money(price, errors, 'invalid_variant_price')
        compare = money(compare, errors, 'invalid_compare_at_price', optional=True)
        if price and compare and Decimal(compare) <= Decimal(price):
            errors.append('invalid_compare_at_price')
        weight = definition.weight_grams if definition.weight_grams is not None else product.weight_grams
        if weight <= 0:
            errors.append('invalid_weight')
        if definition.image_id and not any(i['django_image_id'] == definition.image_id for i in images):
            errors.append('variant_image_not_owned_by_product')
        variants.append({'key': definition.key, 'source_variant_id': definition.source_variant_id,
                         'optionValues': selections, 'price': price, 'compareAtPrice': compare,
                         'sku': definition.sku or product.sku, 'weightGrams': str(weight),
                         'django_image_id': definition.image_id, 'inventoryTracked': False})
    if not is_variant:
        price = money(product.sale_price or product.regular_price, errors, 'invalid_product_price')
        compare = money(product.regular_price if product.sale_price else None, errors, 'invalid_compare_at_price', optional=True)
        if price and compare and Decimal(compare) <= Decimal(price):
            errors.append('invalid_compare_at_price')
        if product.weight <= 0 or product.weight_unit not in ('g', 'kg'):
            errors.append('invalid_weight')
        variants.append({'key': 'default', 'optionValues': [], 'price': price, 'compareAtPrice': compare,
                         'sku': product.sku, 'weightGrams': str(product.weight_grams), 'inventoryTracked': False})
    options = [{'name': name, 'values': list(dict.fromkeys(
        s['value'] for v in variants for s in v['optionValues'] if s['name'] == name))} for name in option_names]
    payload = {'title': product.name, 'handle': f'teraifoods-{product.pk}',
               'descriptionHtml': '<p>' + escape(product.description).replace('\n', '<br>') + '</p>',
               'options': options, 'variants': variants, 'images': images}
    return {'product_id': product.pk, 'name': product.name, 'currency': 'GBP',
            'price': str(product.sale_price or product.regular_price), 'kind': 'variant' if is_variant else 'simple',
            'source_options': metadata.get('source_options', []),
            'source_variant_count': len(source_variants),
            'errors': sorted(set(errors)), 'payload': payload, 'payload_hash': digest(payload)}
