"""Resumable export: python tools/export_rmfoods.py --workers 4."""
import argparse
from collections import Counter
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog.rmfoods import extract_product, normalize
from PIL import Image

BASE = 'https://www.rmfoodswholesale.co.uk'


def fetch(url):
    host = urlsplit(url).hostname
    if host not in ('www.rmfoodswholesale.co.uk', 'static.wixstatic.com'):
        raise ValueError('Unexpected source host')
    result = subprocess.run(['curl', '--fail', '--silent', '--show-error', '--compressed',
                             '--max-time', '60', '--retry', '2', '--retry-delay', '2', url],
                            capture_output=True, check=True)
    return result.stdout


def write_json(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='catalog/data/rmfoods')
    parser.add_argument('--workers', type=int, default=4, choices=range(1, 9))
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    root = Path(args.output)
    for folder in ('records', 'images', 'raw'):
        (root / folder).mkdir(parents=True, exist_ok=True)
    sitemap = fetch(BASE + '/store-products-sitemap.xml')
    (root / 'products-sitemap.xml').write_bytes(sitemap)
    urls = sorted({node.find('{*}loc').text for node in ET.fromstring(sitemap).findall('{*}url')})
    selected = urls[:args.limit] if args.limit else urls
    failures = []

    def export(url):
        slug = urlsplit(url).path.rsplit('/', 1)[-1]
        key = hashlib.sha256(url.encode()).hexdigest()
        output = root / 'records' / (key + '.json')
        if output.exists():
            record = json.loads(output.read_text(encoding='utf-8'))
            if all((root / image['path']).is_file() and
                   hashlib.sha256((root / image['path']).read_bytes()).hexdigest() == image['digest']
                   for image in record['images']):
                return record
        raw_path = root / 'raw' / (key + '.json')
        if raw_path.exists():
            product = json.loads(raw_path.read_text(encoding='utf-8'))
        else:
            try:
                product = extract_product(fetch(url).decode('utf-8'), slug)
            except ValueError:
                # Some public Wix cache entries contain an empty warmup object.
                # A fresh public URL request must still match the exact product slug.
                product = extract_product(fetch(url + '?catalog_export=' + str(int(time.time()))).decode('utf-8'), slug)
            write_json(raw_path, product)
        record = normalize(product, url)
        for image in record['images']:
            # URL hash gives deterministic paths; the content digest validates the asset.
            name = hashlib.sha256(image['url'].encode()).hexdigest() + '.img'
            path = root / 'images' / name
            if path.exists():
                data = path.read_bytes()
                try:
                    with Image.open(io.BytesIO(data)) as probe:
                        probe.verify()
                except (OSError, ValueError):
                    data = fetch(image['url'])
            else:
                data = fetch(image['url'])
            if len(data) > 15 * 1024 * 1024:
                raise ValueError('Image exceeds model upload limit')
            with Image.open(io.BytesIO(data)) as probe:
                image['width'], image['height'] = probe.size
                probe.verify()
            path.write_bytes(data)
            image.update(path='images/' + name, digest=hashlib.sha256(data).hexdigest())
        record['metadata']['fetched_at'] = datetime.now(timezone.utc).isoformat()
        write_json(output, record)
        time.sleep(.15)
        return record

    records = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(export, url): url for url in selected}
        for index, future in enumerate(as_completed(futures), 1):
            try:
                records.append(future.result())
            except Exception as exc:
                failures.append({'url': futures[future], 'error': str(exc)})
            if index % 25 == 0 or index == len(selected):
                print(f'{index}/{len(selected)} processed; {len(records)} exported; {len(failures)} failures', flush=True)
    records.sort(key=lambda record: record['source_url'])
    categories = {c['id']: c for r in records for c in r['categories']}
    report = {'discovered': len(urls), 'attempted': len(selected), 'exported': len(records),
              'images': sum(len(r['images']) for r in records), 'categories': len(categories),
              'review_reasons': dict(Counter(reason for r in records for reason in r['metadata']['review_required'])),
              'products_with_more_than_five_images': sum(len(r['images']) > 5 for r in records),
              'complete': len(records) == len(urls) and not failures, 'failures': failures}
    write_json(root / 'seed.json', {'schema_version': 1, 'source': BASE, 'currency': 'GBP',
                                   'categories': sorted(categories.values(), key=lambda c: c['name']),
                                   'products': records, 'report': report})
    write_json(root / 'report.json', report)
    with (root / 'review.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.writer(stream)
        writer.writerow(['source_key', 'name', 'sku', 'regular_price_gbp', 'sale_price_gbp',
                         'source_categories', 'image_count', 'review_required', 'source_url'])
        for record in records:
            writer.writerow([record['key'], record['name'], record['sku'], record['regular_price'],
                             record['sale_price'], ' | '.join(c['name'] for c in record['categories']),
                             len(record['images']), ' | '.join(record['metadata']['review_required']),
                             record['source_url']])
    print(json.dumps(report), flush=True)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
