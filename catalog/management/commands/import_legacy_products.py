import json
from decimal import Decimal
from pathlib import Path
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify
from catalog.models import Product, Category, Subcategory
from catalog.media import add_image

CATEGORY_ALIASES = {
    'fruits-vegetables':'fruits-veg', 'fruits-and-vegetables':'fruits-veg',
    'meats-seafood':'meats', 'breaksfast-dairy':'breakfast', 'breads-bakery':'bakery',
    'grocery-staples':'grocery', 'household-needs':'household', 'baby-pregnancy':'baby',
    'biscuits-snacks':'snacks', 'frozen-foods':'frozen',
}


class Command(BaseCommand):
    help = 'Import frozen legacy storefront records without overwriting existing products.'

    def add_arguments(self, parser):
        parser.add_argument('--report', default='scratch/product-import-report.json')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        data = json.loads((settings.BASE_DIR / 'catalog/data/legacy-products.json').read_text(encoding='utf-8'))
        report = dict(discovered=len(data['products']), created=0, skipped=0, images=0, published=0,
                      issues=list(data['issues']), records=[])
        for record in data['products']:
            if Product.objects.filter(legacy_key=record['key']).exists():
                report['skipped'] += 1
                continue
            category = Category.objects.filter(legacy_key=record['category']).first() if record['category'] else None
            candidates = record['category_candidates']
            if not category:
                for slug in candidates:
                    category = Category.objects.filter(slug=CATEGORY_ALIASES.get(slug, slug)).first()
                    if category:
                        break
            subcategory = None
            if category:
                matches = list(Subcategory.objects.filter(category=category, slug__in=candidates))
                if len(matches) == 1:
                    subcategory = matches[0]
                elif len(matches) > 1:
                    report['issues'].append(dict(name=record['name'], issue='Multiple source subcategories retained in metadata; assignment needs confirmation'))
            if options['dry_run']:
                continue
            with transaction.atomic():
                metadata = {**record['metadata'], 'legacy_sources':record['sources'],
                            'legacy_ids':record['legacy_ids'], 'legacy_categories':candidates,
                            'legacy_images':record['images'], 'source_price_records':record.get('source_prices', [])}
                product = Product.objects.create(
                    legacy_key=record['key'], name=record['name'], description=record['description'],
                    slug=slugify(record['name'])[:260] + '-' + record['key'][-12:],
                    regular_price=Decimal(record['regular_price']),
                    sale_price=Decimal(record['sale_price']) if record['sale_price'] else None,
                    category=category, subcategory=subcategory, metadata=metadata,
                    display_order=metadata.get('positions', {}).get('shop_0', 100000),
                    rating=Decimal(metadata['rating']) if metadata.get('rating') else None,
                    new_arrival='new_arrival' in record['sections'],
                    featured='featured' in record['sections'] and bool(record['sale_price']),
                    best_seller='best_seller' in record['sections'],
                )
                for url in record['images'][:5]:
                    if not url.startswith('/static/web/'):
                        report['issues'].append(dict(name=record['name'], issue='Unsupported source image URL', image=url))
                        continue
                    source = (settings.BASE_DIR / 'web/static' / url.removeprefix('/static/')).resolve()
                    if not source.is_relative_to((settings.BASE_DIR / 'web/static').resolve()) or not source.is_file():
                        continue
                    try:
                        with source.open('rb') as upload:
                            add_image(product.pk, upload)
                    except ValidationError as exc:
                        report['issues'].append(dict(name=record['name'], issue='Image failed validation', errors=exc.messages))
                    else:
                        report['images'] += 1
                product.is_published = bool(category and product.images.filter(is_main=True).exists())
                product.full_clean()
                product.save()
                report['created'] += 1
                report['published'] += int(product.is_published)
                report['records'].append(dict(id=product.pk, key=record['key'], published=product.is_published, stock='unknown'))
        report['database_total_imported'] = Product.objects.filter(legacy_key__isnull=False).count()
        output = Path(options['report'])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        self.stdout.write(json.dumps({k:v for k,v in report.items() if k not in ('issues', 'records')}))
        self.stdout.write(f'Report: {output}')
