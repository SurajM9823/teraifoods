# Shopify Phase 1: local preview and read-only foundation

Phase 1 adds isolated integration tables, reviewed variant definitions, a read-only
GraphQL client, JSON dry-run previews and sanitized status logs. No Shopify mutation,
product publisher, webhook endpoint, order importer, Celery task, signal, checkout
hook or Stripe modification is included. Shopify jobs are inert records, not a queue
consumer. Creating or enabling a connection does not schedule anything.

## Review safely

Use a disposable local database or database copy. The migrations are generated but
have not been applied to the development or production database by this implementation.
Tests apply migrations only to their isolated test database.

```powershell
.\.venv\Scripts\python.exe manage.py test shopify_integration --settings=config.settings.test
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --settings=config.settings.test
```

After reviewing the migration, apply it ONLY to your chosen disposable database using
the normal project settings for that database. Do not use the in-memory test settings
for interactive review: every command would receive a fresh, empty database.

```powershell
.\.venv\Scripts\python.exe manage.py migrate shopify_integration
.\.venv\Scripts\python.exe manage.py shopify_dry_run 123 456
```

Replace the product IDs with actual local product IDs. No network requests or credentials
are needed. The preview includes name, ID, price, image URLs/alt text, source options,
normalized options/variants, validation codes, proposed draft creation or managed-field
updates, and before/after values. CLI and admin previews do not write database rows
or make network requests. Preview validation status and error codes appear in the output.

The former `--record` option has been removed to keep dry runs strictly read-only.
Explicit variant approval remains a separate write action with a sanitized audit log.
Use `--shop example.myshopify.com` with an existing connection to
compare against its last successfully applied snapshot. Phase 1 never populates that
snapshot from Shopify. `remote_checked=false` is intentional: expected changes are a
local plan, not a live remote diff, nor a directly executable GraphQL mutation input.

There is no `--publish`, `--apply`, `--unpublish`, deletion or archive operation.
New product plans always require draft creation, followed by a separate future
explicit publication action. Existing product status is excluded from managed fields.

## Configuration

No existing `.env` file or production configuration has been modified. These settings
are optional and read by `config/settings/shopify.py`:

| Variable | Default / purpose |
| --- | --- |
| `SHOPIFY_ENABLED` | `false`; gates the read-only API client, not local dry runs |
| `SHOPIFY_SHOP_DOMAIN` | Empty; canonical `example.myshopify.com` hostname |
| `SHOPIFY_API_VERSION` | `2026-10`; must match the connection |
| `SHOPIFY_CLIENT_ID` | Empty; same-organization Dev Dashboard app credentials |
| `SHOPIFY_CLIENT_SECRET` | Empty; read from protected deployment environment/secret manager |
| `SHOPIFY_ACCESS_TOKEN` | Empty; alternative externally provisioned OAuth token |
| `SHOPIFY_MEDIA_ORIGIN` | Empty; public HTTPS origin resolving relative `/media/` image URLs |

Dry runs require no Shopify secrets. Set a local public media origin for valid image
plans, for example `https://teraifoods.co.uk`; without one relative image URLs produce
validation errors. Image URLs are not fetched or proven reachable by Phase 1.

Never put secrets in database rows, source control, admin screenshots or preview files.
Connections contain configuration only. The client accepts only the configured store,
refuses redirects, supports bounded retries, and exposes two allowlisted read queries:
shop information and product identity/status. Arbitrary documents and all mutations
are rejected before token exchange. Access tokens are cached on the client instance,
renewed before expiry, and never stored in shared caches or integration tables.

API access is not needed to approve Phase 1. If later testing reads, use a development
store. The product query needs product read access; future writes require separately
approved scopes and implementation. Same-organization client credentials are supported;
installation/authorization-code callbacks are not implemented. An externally provisioned
token can be supplied for other supported app arrangements.

## Reviewed variants

At `/admin/system/`, authorized staff can edit **Channel variant definitions**. Each row
belongs to a real `catalog.Product` and has:

- A stable local key and original source variant ID.
- Ordered option values, for example `[{"name": "Flavour", "value": "Cola"}]`.
- `inherit` pricing (Django product sale/regular price) OR `explicit` reviewed prices.
- Optional SKU, weight override in grams and a local product image.

When source variant records exist, all original variant IDs must be accounted for
exactly once. Missing/duplicate source identifiers require data review; do not remove
source metadata to bypass errors. Source option IDs, selections and combinations must
be checked by the reviewer against the normalized rows. Approval is a human attestation
of those mappings, not an automatic interpretation of ambiguous source metadata.

Select definitions and run **Preview selected products**. Then, after reviewing the
complete product definition set, use **Approve complete normalized definitions**.
This action approves all definitions for each selected product, not only selected rows.
It requires active staff with change permission on variant definitions. Structural
errors, incomplete mappings, invalid images/prices and unsupported packages block approval.
Approval does not contact Shopify. Re-run the CLI preview to verify zero errors.

The stored review fingerprint covers source options/variants, normalized definitions,
product price, weight and inherited SKU. Changes invalidate approval. Original `Product.metadata` is
never rewritten. Simple products need no variant rows or variant review. A single
source default item with no selections remains a simple product.
The audit fixes changed the fingerprint format; existing approvals need a fresh review.
Malformed source variant entries (including a single null entry) block the preview
instead of being treated as a simple default variant.

## Data model and isolation

`0001_initial` creates only integration-owned tables: connection, variant definition,
variant review, product/variant/media mappings, inert sync jobs, webhook receipts,
order/order-line staging mappings and integration logs. It depends on catalogue
migration `0012` and the configured user model. It does not alter catalogue, order,
payment or stock tables. Follow-up migration `0002_allow_local_image_deletion` makes
integration image references nullable with `SET_NULL`, so the existing product image
editor can delete images normally. Media mappings retain their remote identity/digest;
deleting a reviewed variant image invalidates approval and requires another review.
Future synchronization must handle detached mappings explicitly, without automatically
deleting remote media.

Order mappings have a database-constrained `sales_channel='shopify'` and unique
shop/remote-order identity. Their optional local order link is reserved for a later
importer; Phase 1 neither creates nor links operational orders. Do not manually create
linked operational Shopify orders: existing payment, cancellation and stock-restoration
paths are not yet channel-aware. Customer payload fields in the staging schema are
reserved for future work and have no receiving endpoint or admin editing action.

The mapping/log admin is read-only. Variant definitions and connection configuration
are editable; tokens and secrets have no admin fields. No Django customer accounts,
stock audits, payments or customer notifications are created by previews/reviews.

## Known limits and approval gate

- Packages are blocked pending a reviewed package policy.
- Local previews do not inspect remote drift, image availability, tax configuration,
  Shopify currency, publication availability or granted scopes.
- GBP is the current catalogue currency. No currency conversion is attempted.
- Existing source variant records are not automatically copied into approved definitions.
- No automatic publishing, unpublishing, archiving or deletion exists.
- Webhook verification, import workers, channel-aware operational guards, privacy
  retention and fulfilment synchronization remain future phases.
- SQLite tests are fast isolated checks. PostgreSQL validation is still required
  before production rollout.

Review the additive migration, test output, simple and blocked-variant previews,
and review-invalidation behaviour. Approval of this phase does not authorize live
publication, real order imports, deployment, or Phase 2 implementation.

Official API references used for the foundation:
[GraphQL Admin API](https://shopify.dev/docs/api/admin-graphql/latest),
[client credentials](https://shopify.dev/docs/apps/build/authentication-authorization/client-credentials-grant).

## Implementation verification (2026-10-30)

- Final integration suite: 30 tests passed using `config.settings.test`.
- Combined integration, `orders.test_embedded`, `orders.test_live_payments` and
  `catalog.test_products` run: 78 tests passed before the final three integration
  cases were added. The final integration suite was rerun after those changes.
- `makemigrations --check --dry-run`: no changes detected.
- Django `check`: no issues.
- All API responses in tests are mocked. No live Shopify requests were executed.
- No application/production database migration, environment modification or deployment
  was performed. PostgreSQL execution and live-store checks remain outstanding.

## Audit fixes verified (2026-10-30)

- CLI, service and admin dry runs no longer persist preview logs. The `--record`
  option was removed. Tests reject SQL writes and socket connections during previews.
- Nullable integration image references preserve the existing main-image replacement/
  deletion workflow. Deletion clears references, retains remote media identity, and
  invalidates the affected variant approval.
- Malformed source variant records fail validation. Effective inherited SKU changes
  invalidate approval; unrelated product SKU changes do not affect explicit variant SKUs.
- 84 tests passed: 34 integration tests plus existing embedded-checkout, live-payment
  and `catalog.test_products.ProductTests` coverage. To respect the no-migrations
  constraint, this run created the current model schema directly in disposable
  in-memory SQLite and supplied two baseline category fixtures. An initial run
  without those fixtures failed existing payment setup; the fixture-corrected run passed.
- Django system check, migration-state comparison and Git whitespace check passed.
  No migration executor, application database, Shopify API or deployment was used.
  PostgreSQL and actual migration execution remain unverified.
