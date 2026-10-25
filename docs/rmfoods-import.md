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
Existing products are identified by `legacy_key = rmfoods:<source UUID>` and are
never overwritten. Matching category names are reused case-insensitively.

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
- The source has overlapping collections, not a clean two-level taxonomy.
  Collection names are preserved as categories. The smallest non-promotional
  source collection is selected as the product category, with review flagged.
  Subcategory remains unset. No hierarchy is invented or existing taxonomy removed.
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
checksum failure before database writes.
