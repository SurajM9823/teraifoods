import copy
import json
from pathlib import Path
from django.core.exceptions import ValidationError
from django.http import Http404
from .api import public_products, paginate, serialize
from .packages import present

LAYOUTS = json.loads((Path(__file__).parent / 'data/layouts.json').read_text(encoding='utf-8'))


def context(request, page_key):
    prefix = {'home':'index', 'shop':'shop', 'search':'shop', 'product':'product', 'product-detail':'product_detail', 'package':'product_detail', 'package-detail':'product_detail'}.get(page_key)
    if not prefix:
        return {}
    from .models import CatalogRevision
    revision, _ = CatalogRevision.objects.get_or_create(pk=1)
    result = {'catalog_groups':{}, 'catalog_revision': revision.version, 'search_query': request.GET.get('q', request.GET.get('s', '')).strip()}
    selected = None
    if prefix in ('product', 'product_detail'):
        from delivery.models import DeliveryPolicy
        result['delivery_policy'] = DeliveryPolicy.objects.filter(pk=1).first()
        slug = request.GET.get('product')
        selected = public_products().filter(slug=slug).first() if slug else public_products().filter(metadata__legacy_detail=True).first()
        if slug and selected is None:
            raise Http404('Product not available')
        selected=present(selected)
        result['product'] = selected
        result['product_payload'] = serialize(selected) if selected else None
        if selected and selected.is_package:
            result['is_package'] = True
            result['bundle_lines'] = getattr(selected, 'bundle_lines', [])
            result['bundle_savings'] = getattr(selected, 'bundle_savings', 0)
            result['bundle_items_count'] = getattr(selected, 'bundle_items_count', 0)
            result['bundle_products_count'] = getattr(selected, 'bundle_products_count', 0)
            result['package_config'] = getattr(selected, 'package_config', None)
    for group, layout in LAYOUTS.items():
        if not group.startswith(prefix + '_'):
            continue
        if layout['section'] == 'for_you':
            rows, info = paginate({'section': 'for_you', 'limit': '24', 'group': 'index_3'})
            result['catalog_for_you_page'] = info
        elif layout['listing']:
            try:
                rows, info = paginate(request.GET)
            except ValidationError:
                rows, info = [], dict(next_cursor=None, has_more=False, total=0)
            result['catalog_page'] = info
        else:
            queryset = public_products()
            if layout['section'] in ('new_arrival', 'featured', 'best_seller'):
                queryset = queryset.filter(**{layout['section']:True})
            if selected:
                queryset = queryset.exclude(pk=selected.pk)
            # Original ordering is presentation metadata, not a second catalog.
            rows = sorted(queryset[:200], key=lambda p:(p.metadata.get('positions', {}).get(group, 100000), p.pk))[:layout['limit']]
        result['catalog_groups'][group] = []
        for row in rows:
            product = present(copy.copy(row))
            template = product.metadata.get('cards', {}).get(group, layout['template'])
            # Only generated, repository-owned templates may be selected.
            product.card_template = template if template.startswith('catalog/storefront/card_') and '..' not in template else layout['template']
            result['catalog_groups'][group].append(product)
    return result
