"""One-time source audit. Uses spans so the approved HTML is not reformatted."""
import hashlib
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOID = {'img', 'input', 'br', 'hr', 'meta', 'link', 'source', 'area', 'embed', 'wbr', 'col', 'base', 'param'}


class Node:
    def __init__(self, tag, attrs, start, open_end, parent=None):
        self.tag, self.attrs, self.start, self.open_end = tag, dict(attrs), start, open_end
        self.end = self.close_start = open_end
        self.parent, self.children = parent, []

    def has(self, cls):
        return cls in self.attrs.get('class', '').split()

    def all(self):
        for child in self.children:
            yield child
            yield from child.all()

    def find(self, cls):
        return next((n for n in self.all() if n.has(cls)), None)


class Parser(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.offsets = [0] + [m.end() for m in re.finditer('\n', source)]
        self.root = Node('root', [], 0, 0)
        self.stack = [self.root]
        self.feed(source)

    def pos(self):
        line, col = self.getpos()
        return self.offsets[line - 1] + col

    def handle_starttag(self, tag, attrs):
        start = self.pos()
        node = Node(tag, attrs, start, start + len(self.get_starttag_text()), self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack[-1].tag == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                node = self.stack[i]
                node.close_start = self.pos()
                node.end = self.source.find('>', node.close_start) + 1
                self.stack = self.stack[:i]
                break


def text(source, node):
    if node is None:
        return ''
    return html.unescape(re.sub(r'<[^>]+>', '', source[node.open_end:node.close_start])).strip()


def price(source, node):
    values = re.findall(r'\d+(?:\.\d{1,2})?', text(source, node).replace(',', ''))
    return values[-1] if values else None


def asset(value):
    return re.sub(r"{%\s*static\s+'web/'\s*%}", '/static/web/', value)


def extract():
    records, occurrences, issues = {}, [], []
    for path in sorted((ROOT / 'web/templates/web').glob('*.html')):
        source = path.read_text(encoding='utf-8')
        parser = Parser(source)
        for node in parser.root.all():
            if not (node.has('shop-product-card') or node.has('type-product')):
                continue
            title = text(source, node.find('product-title'))
            if not title:
                continue
            key = 'legacy-' + hashlib.sha256(title.casefold().encode()).hexdigest()[:24]
            img = next((n for n in node.all() if n.tag == 'img'), None)
            sale_node = node.find('sale-price') or next((n for n in node.all() if n.tag == 'ins'), None)
            regular_node = node.find('regular-price') or next((n for n in node.all() if n.tag == 'del'), None)
            current = price(source, sale_node or node.find('price') or node.find('range-price'))
            regular = price(source, regular_node) or current
            if not regular:
                existing = records.get(key)
                if existing:
                    current, regular = existing['sale_price'], existing['regular_price']
            if not regular:
                issues.append({'source': str(path.relative_to(ROOT)), 'name': title, 'issue': 'Missing price'})
                continue
            legacy_id = next((n.attrs['data-product_id'] for n in node.all() if 'data-product_id' in n.attrs), '')
            prefix = source[:node.start]
            headings = re.findall(r'<h[23][^>]*>(.*?)</h[23]>', prefix, re.S)
            section = ''
            for heading in reversed(headings):
                clean = html.unescape(re.sub('<[^>]+>', '', heading)).strip().lower()
                if clean in ('new arrivals', 'featured products', 'best sellers', 'for you'):
                    section = {'new arrivals':'new_arrival', 'featured products':'featured', 'best sellers':'best_seller', 'for you':'for_you'}[clean]
                    break
            category = node.attrs.get('data-category', '')
            cats = re.findall(r'product_cat-([\w-]+)', node.attrs.get('class', ''))
            image = asset(img.attrs.get('src', '')) if img else ''
            record = records.setdefault(key, dict(key=key, name=title, regular_price=regular,
                sale_price=current if sale_node and current != regular else None,
                images=[], category=category, category_candidates=cats, sections=[],
                description='', legacy_ids=[], sources=[], source_prices=[], metadata={}))
            record['source_prices'].append(dict(source=str(path.relative_to(ROOT)), regular_price=regular, sale_price=current))
            if category and not record['category']:
                record['category'] = category
            if image and image not in record['images']:
                record['images'].append(image)
            if legacy_id and legacy_id not in record['legacy_ids']:
                record['legacy_ids'].append(legacy_id)
            if section and section not in record['sections']:
                record['sections'].append(section)
            origin = str(path.relative_to(ROOT)).replace('\\', '/')
            if origin not in record['sources']:
                record['sources'].append(origin)
            if regular != record['regular_price']:
                issues.append(dict(name=title, issue='Conflicting source price', source=origin, regular_price=regular))
            record['metadata'].setdefault('rating', node.attrs.get('data-rating', text(source, node.find('rating')) or ''))
            occurrences.append(dict(source=origin, start=node.start, end=node.end, key=key,
                parent_start=node.parent.start, section=section, shop=node.has('shop-product-card')))
    # Wishlist seed is a separate source, including a known absent image.
    js = (ROOT / 'web/static/web/js/terai-interactive.js').read_text(encoding='utf-8')
    block = re.search(r'const DEFAULT_WISHLIST = \[(.*?)\n  \];', js, re.S)
    if block:
        for raw in re.findall(r'\{(.*?)\}', block[1], re.S):
            fields = dict(re.findall(r'(\w+):\s*[\'"]([^\'"\n]*)[\'"]', raw))
            title_match = re.search(r'title:\s*"([^"]+)"', raw)
            title = title_match[1] if title_match else fields.get('title', '')
            key = 'legacy-' + hashlib.sha256(title.casefold().encode()).hexdigest()[:24]
            money = dict(re.findall(r'(price|oldPrice):\s*([\d.]+)', raw))
            records.setdefault(key, dict(key=key, name=title, regular_price=money.get('oldPrice', money.get('price')),
                sale_price=money.get('price') if money.get('oldPrice') else None, images=[fields.get('image', '')],
                category='', category_candidates=[], sections=[], description='', legacy_ids=[fields.get('id')],
                sources=['web/static/web/js/terai-interactive.js'], metadata={'unit':fields.get('unit', '')}))
    # Dedicated detail page is a separate product, never silently mapped to a card.
    path = ROOT / 'web/templates/web/product-detail.html'
    source = path.read_text(encoding='utf-8')
    parser = Parser(source)
    title = text(source, parser.root.find('pdp-product-title'))
    if title:
        key = 'legacy-' + hashlib.sha256(title.casefold().encode()).hexdigest()[:24]
        images = [asset(n.attrs['data-img']) for n in parser.root.all() if 'data-img' in n.attrs]
        narrative = parser.root.find('pdp-narrative')
        paragraphs = [text(source, n) for n in narrative.all() if n.tag == 'p'] if narrative else []
        records[key] = dict(key=key, name=title, regular_price='5.50', sale_price='4.19', images=list(dict.fromkeys(images)),
            category='grocery', category_candidates=['spices-seasonings'], sections=[], description='\n\n'.join(paragraphs), legacy_ids=[],
            sources=['web/templates/web/product-detail.html'], metadata={'legacy_detail':True, 'stock_conflict':'14 items / 38 left'})
    for record in records.values():
        for image in record['images']:
            local = ROOT / 'web/static' / image.removeprefix('/static/')
            if not local.is_file():
                issues.append(dict(name=record['name'], issue='Missing image', image=image))
        if not record['category'] and not record['category_candidates']:
            issues.append(dict(name=record['name'], issue='Category requires confirmation'))
    return dict(products=list(records.values()), occurrences=occurrences, issues=issues)


if __name__ == '__main__':
    result = extract()
    destination = ROOT / 'catalog/data/legacy-products.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(dict(products=len(result['products']), occurrences=len(result['occurrences']), issues=len(result['issues']))))
