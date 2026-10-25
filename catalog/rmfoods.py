"""RM Foods public-page extraction. No database or network side effects on import."""
import json
import re
from decimal import Decimal
from html import unescape
from html.parser import HTMLParser


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.capture = dict(attrs).get('id') == 'wix-warmup-data'

    def handle_endtag(self, tag):
        if tag == 'script':
            self.capture = False

    def handle_data(self, data):
        if self.capture:
            self.parts.append(data)


def dictionaries(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from dictionaries(child)
    elif isinstance(value, list):
        for child in value:
            yield from dictionaries(child)


def extract_product(html, slug):
    parser = Scripts()
    parser.feed(html)
    data = json.loads(''.join(parser.parts))
    for obj in dictionaries(data):
        if obj.get('urlPart') == slug and 'price' in obj and 'productItems' in obj:
            return obj
    raise ValueError('Matching structured product not found')


def plain_text(value):
    if not value:
        return ''
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return unescape(re.sub('<[^>]+>', '', value)).strip()
    if not isinstance(value, dict):
        return ''
    if 'textData' in value:
        return value['textData'].get('text', '')
    kind = value.get('type')
    separator = '\t' if kind == 'TABLE_ROW' else '\n' if kind in (None, 'TABLE', 'BULLETED_LIST', 'ORDERED_LIST') else ''
    return separator.join(plain_text(child) for child in value.get('nodes', [])).strip()


def normalize(product, url):
    regular = Decimal(str(product['price']))
    discounted = Decimal(str(product.get('discountedPrice') or regular))
    if not regular.is_finite() or regular <= 0:
        raise ValueError('Missing or invalid regular price')
    issues = ['shipping_weight_unverified', 'local_stock_unconfirmed']
    if product.get('options'):
        issues.append('options_require_review')
    images = []
    for media in product.get('media', []):
        if media.get('mediaType') == 'PHOTO' and media.get('fullUrl'):
            images.append({'url': media['fullUrl'], 'alt': media.get('altText') or product['name']})
    if not images:
        issues.append('missing_images')
    return {
        'key': 'rmfoods:' + product['id'], 'source_url': url,
        'name': product['name'], 'slug': product['urlPart'], 'sku': product.get('sku') or '',
        'description': plain_text(product.get('description')),
        'regular_price': str(regular.quantize(Decimal('.01'))),
        'sale_price': str(discounted.quantize(Decimal('.01'))) if 0 < discounted < regular else None,
        'categories': product.get('categories', []), 'images': images,
        'metadata': {
            'source': 'rmfoods', 'source_url': url, 'source_currency': 'GBP',
            'brand': product.get('brand'), 'review_required': issues,
            'source_categories': product.get('categories', []),
            'source_inventory': product.get('inventory'),
            'source_options': product.get('options', []),
            'source_variants': product.get('productItems', []),
            'source_ribbon': product.get('ribbon'),
            'additional_information': [{'title': section.get('title'), 'text': plain_text(section.get('description'))}
                                       for section in product.get('additionalInfo', [])],
        },
    }
