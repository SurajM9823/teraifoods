# RM Foods catalogue seed

The exporter reads public product pages listed in RM Foods' product sitemap. It
extracts the matching product's embedded structured data, downloads its photos,
and saves a portable seed next to the image directory. It does not change the
application database. A separate Django command imports the seed.

## Included snapshot (25 October 2026)

All 2,612 sitemap product URLs exported successfully, with 3,274 image references
and 254 source collections. Ten products have no source photos, 30 have selectable
options requiring review, and 24 have more than the model's five-image limit.
Shipping weights and your local inventory require confirmation for every product.
The complete seed passed model-field validation and image-checksum verification.

## Export or resume

```powershell
.venv\Scripts\python tools/export_rmfoods.py --workers 8
```

Requires Python, Pillow (already in the project dependencies), and `curl` on PATH.
Use fewer workers to reduce traffic. Successfully completed records are reused;
failed records are retried on the next run. Source product JSON is cached to avoid
downloading pages again when an image fails. Use a new `--output` directory for a
fresh price snapshot; resuming deliberately preserves previously fetched prices.

Output is under `catalog/data/rmfoods/`:

- `seed.json`: portable versioned product and category data.
- `images/`: downloaded photos, with checksums recorded in the seed.
- `report.json`: discovered/exported counts and URLs that failed.
- `review.csv`: spreadsheet-friendly prices, categories and missing-data flags.
- `records/` and `raw/`: resumable intermediate files and source product data.
- `products-sitemap.xml`: discovery snapshot.

The seed and images must travel together. Do not use Django `loaddata` on this
file; its importer handles category matching and your image processing pipeline.

## Validate and import

```powershell
.venv\Scripts\python manage.py import_rmfoods --dry-run
.venv\Scripts\python manage.py import_rmfoods
```

`--seed PATH` selects another seed. `--limit 10` permits a small trial. Dry-run
checks model field values and all image file checksums without database writes.
Import is transactional per product; completed products are skipped on rerun.
Existing products are matched by `legacy_key = rmfoods:<source UUID>`, normalized
exact name, or nonempty SKU and are never overwritten. Name comparison ignores
case and repeated whitespace, but preserves pack sizes and punctuation; there is
no fuzzy matching. Repeated source entries are skipped too. Matching category
names are reused case-insensitively.

Products are created as **drafts**, with stock zero and stock unconfirmed. Review
and set your own stock, prices and shipping weights before publishing.

## Mapping and limits

- Name, SKU, description, regular price and discounted price map to model fields.
  Prices remain GBP; there is no currency conversion or VAT recalculation.
- Images pass through `catalog.media.add_image`, generating the existing JPEG,
  WebP and AVIF sizes. The model permits five photos per product; all downloaded
  photos remain in the seed, and only the first five attach to the product.
- Brand, ingredients, nutritional information, other information, original
  collection memberships, options, variants, availability, source URL and fetch
  time remain in `metadata`. These metadata fields are not automatically displayed
  on the storefront.
- Source collections include merchandise types, brands and promotions. The importer
  now uses the explicit mapping in `catalog/rmfoods_taxonomy.py`, checked against
  the source navigation on 25 October 2026. It assigns both category and subcategory:
  e.g. Energy Drinks / Monster Energy, Coffee / Coffee Sachets / Blends, and
  Snacks & Chocolates / Chocolate Bars. Energy Drinks remains its own main group
  because the local model supports two levels and the source gives it a dedicated menu.
  Other merchandise is grouped into Sauces, Cereals, Biscuits, Toiletries, Pet Foods,
  Spices, Lentils, Tea, Cleaning Products, Containers and Food Cupboard.
- Existing category/subcategory records are reused, preserving inactive status.
  Brands and promotional collections are not created as main categories. Best Offers
  and Most Popular retain their source membership as metadata and storefront filters.
  Name-based recovery for missing or demonstrably incorrect source types is flagged
  `category_inferred_from_name`; it should be reviewed before publication. Original
  source memberships remain intact in metadata.
- Shipping weight is unverified: the model's required 150 g default is only a
  placeholder, explicitly marked in `metadata.review_required`. Pack volume is
  not treated as shipping mass. Replace this before publishing.
- Variable products remain one draft with options and variant records in metadata.
  The current model has no native product-option field. These need review before
  they can be sold correctly.
- Source availability is informational; it is not your warehouse inventory.
  Source reviews are not imported as customer reviews.

Completeness is reported against the public sitemap snapshot, not hidden or
unpublished products. `report.complete` is true only when every discovered URL
exports successfully. Export prices reflect each page's fetch time.

## Tests

```powershell
.venv\Scripts\python manage.py test catalog.test_rmfoods --settings=config.settings.test
```

Tests cover source-product matching, rich text tables, discounted prices,
dry-run, draft defaults, repeat imports, preservation of staff edits, and image
checksum failure before database writes. They also cover two-level mappings,
brand/type conflicts, missing source memberships, preservation of inactive categories,
repair idempotency, promotional filtering and cursor isolation.

## Repair an earlier flat import

Run these commands in the intended database environment. The default command only
plans changes; back up that database before applying. The usual native wrapper uses
the live database unless its settings are explicitly overridden.

```bash
python manage.py repair_rmfoods_categories --report category-plan.json
python manage.py repair_rmfoods_categories --apply --report category-result.json
```

The repair only changes imported products' category, subcategory and mapping metadata.
It keeps prices, publication, inventory, images and owner edits to other fields. It
deactivates unused imported flat categories, retaining their records; manual categories
and categories still in use are preserved. It does not import missing products or
redownload images. The report identifies inferred assignments for review. Restart any
preview process using an in-memory cache after repair; normal deployments invalidate
the configured category/revision caches.

## Promote the reviewed preview

The reviewed exporter includes only RM Foods catalogue fields, categories,
subcategories and prepared-image references. It excludes users, orders, sessions
and settings. Export using the server environment, then plan the import against
the live database. Back up the live database and media before applying.

```bash
.venv/bin/python deploy/native/manage.py export_rmfoods_reviewed \
  --source-database teraifoods_rmfoods_trial_20261025t171331z \
  --output scratch/reviewed.json
.venv/bin/python deploy/native/manage.py import_rmfoods_reviewed \
  --catalog scratch/reviewed.json --media-root scratch/preview/media \
  --report scratch/promotion-plan.json
# After reviewing the plan and taking backups, run as the application user:
sudo -u teraifoods .venv/bin/python deploy/native/manage.py import_rmfoods_reviewed \
  --catalog scratch/reviewed.json --media-root scratch/preview/media \
  --apply --report scratch/promotion-result.json
```

Give the application user read access to the export/source media and write access
to the report location. The command validates paths and existing image contents,
copies prepared variants without re-encoding, and never overwrites existing media.
It imports new products in one database transaction and rechecks duplicate matches
after preparing images. Existing products retain their prices, inventory, images,
publication and metadata. Existing category/subcategory active status is preserved.
New products retain their reviewed publication status and unconfirmed stock. A
repeat run creates no additional products. Backups and reports stay outside Git.

For a local checkout, pull the pushed code first. If the reviewed catalogue and
prepared images are needed locally, copy `scratch/live-promotion/reviewed.json`
and the retained server `scratch/preview/media/` contents into local
`scratch/reviewed.json` and `scratch/reviewed-media/`, then use
`manage.py import_rmfoods_reviewed` with those
paths and the local database environment. The Git push synchronizes code; it does
not replace a local database or transfer uploaded media.
