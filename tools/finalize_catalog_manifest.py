"""Resolve demonstrable aliases; retain every original spelling and price."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'catalog/data/legacy-products.json'
data = json.loads(path.read_text(encoding='utf-8'))


def normalized(name):
    return re.sub(r'\s+', ' ', name.casefold().replace('’', "'").replace('–', '-').replace('—', '-')).strip()


products, aliases = [], {}
for record in data['products']:
    name = normalized(record['name']).removesuffix('...')
    match = next((p for p in products if p['images'] and p['images'][0] in record['images']
                  and (normalized(p['name']) == name or normalized(p['name']).startswith(name))), None)
    if match:
        aliases[record['key']] = match['key']
        match['metadata'].setdefault('legacy_names', [match['name']]).append(record['name'])
        for field in ('legacy_ids', 'sources', 'sections', 'images', 'category_candidates'):
            match[field] = list(dict.fromkeys(match[field] + record[field]))
        match.setdefault('source_prices', []).extend(record.get('source_prices', []))
        for field in ('cards','positions'):
            match['metadata'].setdefault(field, {}).update(record['metadata'].get(field, {}))
        if record['category'] and not match['category']:
            match['category'] = record['category']
    else:
        products.append(record)

for occurrence in data['occurrences']:
    occurrence['key'] = aliases.get(occurrence['key'], occurrence['key'])
for record in products:
    # Shop prices take precedence when demos disagree; every source remains in
    # source_prices. This policy applies only to a new import, never real records.
    shop = next((p for p in record.get('source_prices', []) if p['source'].replace('\\','/') == 'web/templates/web/shop.html'), None)
    if shop:
        record['regular_price'] = shop['regular_price']
        record['sale_price'] = shop['sale_price'] if shop['sale_price'] != shop['regular_price'] else None
    if record['name'] == 'Cantaloupe Melon Fresh Organic Cut':
        record['metadata']['legacy_price_range'] = {'minimum':'1.25','maximum':'1.50'}
        record['metadata']['variant_confirmation_required'] = True
        record['regular_price'] = '1.25'
        record['sale_price'] = None
        data['issues'].append({'name':record['name'], 'issue':'Legacy variable-price product: £1.25–£1.50. Confirm sellable variant and stock before purchase.'})
data['products'] = products
data['aliases'] = aliases
path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'unique_products':len(products),'merged_aliases':len(aliases)}))
