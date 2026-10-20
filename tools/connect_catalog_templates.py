"""Parameterize original card spans; never reserialize or reformat page HTML."""
import json
import re
from collections import defaultdict
from extract_catalog import ROOT, Parser, text


def parameterize(raw):
    parser = Parser(raw)
    changes = []
    title = parser.root.find('product-title')
    if title:
        link = next((n for n in title.all() if n.tag == 'a'), title)
        changes.append((link.open_end, link.close_start, '{{ product.name }}'))
    for node in parser.root.all():
        start = raw[node.start:node.open_end]
        start = re.sub(r'data-product_id="[^"]*"', 'data-product_id="{{ product.pk }}"', start)
        start = re.sub(r'data-(?:product_title|product_name|name)="[^"]*"', 'data-name="{{ product.name }}"', start)
        start = re.sub(r'aria-label="Add to cart:[^"]*"', 'aria-label="Add {{ product.name }} to cart"', start)
        start = re.sub(r'data-success_message="[^"]*"', 'data-success_message="{{ product.name }} added to cart"', start)
        start = re.sub(r'data-price="[^"]*"', 'data-price="{{ product.price }}"', start)
        start = re.sub(r'data-category="[^"]*"', 'data-category="{{ product.category.legacy_key|default:product.category.slug }}"', start)
        start = re.sub(r'(post-|klbwl-btn-|klbcp-btn-)\d+', r'\1{{ product.pk }}', start)
        start = re.sub(r'\?add-to-cart=\d+', '?add-to-cart={{ product.pk }}', start)
        start = re.sub(r'href="{% url \'web:product-detail\' %}"', 'href="/product-detail/?product={{ product.slug }}"', start)
        if node.has('type-product') or node.has('shop-product-card'):
            start = start[:-1] + ' data-catalog-product="{{ product.pk }}" data-product-url="/product-detail/?product={{ product.slug }}">'
        if node.tag == 'img':
            start = re.sub(r'src="[^"]*"', 'src="{{ product.image_url }}"', start)
            start = re.sub(r'srcset="[^"]*"', 'srcset="{{ product.main_image.webp_srcset }}"', start)
            start = re.sub(r'alt="[^"]*"', 'alt="{{ product.name }}"', start)
            if 'loading=' not in start:
                start = start[:-1] + ' loading="lazy" decoding="async">'
            start = '<picture><source type="image/avif" srcset="{{ product.main_image.avif_srcset }}" sizes="(max-width: 500px) 50vw, 250px"><source type="image/webp" srcset="{{ product.main_image.webp_srcset }}" sizes="(max-width: 500px) 50vw, 250px">' + start + '</picture>'
        if start != raw[node.start:node.open_end]:
            changes.append((node.start,node.open_end,start))
        if node.has('sale-price'):
            changes.append((node.open_end,node.close_start,'&pound;{{ product.price }}'))
        elif node.has('regular-price'):
            changes.append((node.open_end,node.close_start,'{% if product.sale_price %}&pound;{{ product.regular_price }}{% endif %}'))
        elif node.has('range-price'):
            changes.append((node.open_end,node.close_start,'&pound;{{ product.price }}'))
        elif node.tag == 'bdi':
            # Preserve the original currency span and replace only the amount.
            currency = next((n for n in node.children if n.has('woocommerce-Price-currencySymbol')), None)
            parent = node.parent
            is_old = False
            while parent:
                is_old = is_old or parent.tag == 'del'
                parent = parent.parent
            changes.append((currency.end if currency else node.open_end,node.close_start,
                            '{{ product.regular_price }}' if is_old else '{{ product.price }}'))
        elif node.has('badge-discount') or (node.has('badge') and node.has('sale')):
            changes.append((node.open_end,node.close_start,'{{ product.discount_percent }}%'))
        elif node.has('screen-reader-text') and ('price' in text(raw,node).lower()):
            changes.append((node.open_end,node.close_start,'Price: &pound;{{ product.price }}'))
    # Replace outer spans first only when they do not overlap a chosen inner span.
    selected = []
    for a,b,value in sorted(changes, key=lambda row:(row[0], -(row[1]-row[0]))):
        if selected and a < selected[-1][1]:
            continue
        selected.append((a,b,value))
    for a,b,value in reversed(selected):
        raw = raw[:a]+value+raw[b:]
    return '{% load static %}\n' + raw


def main():
    manifest_path = ROOT / 'catalog/data/legacy-products.json'
    data = json.loads(manifest_path.read_text(encoding='utf-8'))
    records = {p['key']:p for p in data['products']}
    templates = ROOT / 'catalog/templates/catalog/storefront'
    templates.mkdir(parents=True, exist_ok=True)
    grouped = defaultdict(list)
    for occurrence in data['occurrences']:
        grouped[occurrence['source']].append(occurrence)
    definitions = {}
    for filename, occurrences in grouped.items():
        path = ROOT / filename
        source = path.read_text(encoding='utf-8')
        parser = Parser(source)
        nodes = {n.start:n for n in parser.root.all()}
        groups = defaultdict(list)
        for occurrence in occurrences:
            node = nodes[occurrence['start']]
            container = node.parent.parent if node.parent.has('slider-item') else node.parent
            groups[container.start].append((occurrence,node))
        changes = []
        for group_index, items in enumerate(groups.values()):
            group = f'{path.stem.replace("-","_")}_{group_index}'
            definitions[group] = dict(section=items[0][0]['section'], limit=len(items),
                                      listing=path.stem=='shop', related=path.stem in ('product','product-detail'))
            starts, ends = [], []
            for index,(occurrence,node) in enumerate(items):
                wrapper = node.parent if node.parent.has('slider-item') else node
                starts.append(wrapper.start); ends.append(wrapper.end)
                template = f'catalog/storefront/card_{group}_{index}.html'
                raw = source[wrapper.start:wrapper.end]
                (ROOT / 'catalog/templates' / template).write_text(parameterize(raw), encoding='utf-8')
                record = records[occurrence['key']]
                record['metadata'].setdefault('cards', {})[group] = template
                record['metadata'].setdefault('positions', {})[group] = index
                if index == 0:
                    definitions[group]['template'] = template
            replacement = "{% for product in catalog_groups." + group + " %}{% include product.card_template %}{% endfor %}"
            changes.append((min(starts),max(ends),replacement))
        for start,end,value in sorted(changes, reverse=True):
            source = source[:start]+value+source[end:]
        path.write_text(source, encoding='utf-8')
    (ROOT / 'catalog/data/layouts.json').write_text(json.dumps(definitions,indent=2),encoding='utf-8')
    manifest_path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    shop = next(v for v in definitions.values() if v['listing'])
    (templates / 'shop_cards.html').write_text('{% for product in products %}{% include "'+shop['template']+'" %}{% endfor %}',encoding='utf-8')
    print(f'Connected {len(data["occurrences"])} cards in {len(definitions)} groups without changing page styles.')


if __name__ == '__main__':
    main()
