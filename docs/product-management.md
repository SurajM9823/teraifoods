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

The initial audit encountered unavailable PostgreSQL and Docker. Docker is now
running locally, migrations and the legacy product import are applied, and the
PostgreSQL suite passed, including concurrent stock and checkout tests. Local
demo payments are available. Actual Stripe connection, remote deployment and
external CDN setup remain separate; see `order-management.md` for current status.
