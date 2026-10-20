# Product management implementation

Customer storefront design is frozen. Existing uncommitted changes are the
baseline; do not revert them. Original templates and interactive script were
copied to `scratch/product-baseline/` before implementation.

## Audit and execution plan

1. Django 5.2 server-rendered templates; PostgreSQL in normal environments.
   Existing `catalog` category/subcategory models, protected relationships,
   custom permission-checked category dashboard, Redis category cache, Pillow,
   filesystem media storage, Nginx and Docker deployment are reused.
2. Add products, images, optional homepage section flags, inventory audits and
   order reservations. Use decimal prices, database constraints, row locks,
   idempotency keys and protected foreign keys.
3. Extend the existing staff dashboard with product editing, image operations,
   stock adjustments and history. Add public paginated read APIs and
   authenticated checkout validation/reservation.
4. Inventory all template and JavaScript product sources in an immutable import
   manifest, preserving conflicts as distinct records. Import idempotently,
   report unknown stock/category/image data rather than fabricate it.
5. Parameterize existing product markup and connect filtering/pagination.
   Preserve customer CSS, card wrappers, grid classes and page structure.
6. Generate content-addressed AVIF/WebP/JPEG images, cache public queries with
   versioned namespaces and graceful Redis fallback.
7. Run isolated functional/browser checks and document production-only checks.

## Environment limitations at audit

Local PostgreSQL connection times out and Docker Desktop is not running.
The isolated preview uses `scratch/catalog-preview.sqlite3` via an explicit
scratch settings module. This never substitutes SQLite in normal settings.
CDN credentials/provider and payment gateway are not configured in this task.
Do not claim production import, PostgreSQL concurrency, payment processing or
global CDN delivery based on isolated tests.
