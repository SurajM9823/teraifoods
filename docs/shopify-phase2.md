# Shopify Phase 2: explicit draft synchronization

Phase 2 adds an explicit product-to-draft operation. It does not publish, unpublish,
archive or delete products and does not import orders or invoke local checkout,
Stripe, stock adjustments, refunds, customer accounts or customer emails.

## Configuration and permissions

Keep the existing server-only Shopify credentials. Add
`SHOPIFY_DRAFT_SYNC_ENABLED=true` to the protected deployment environment only when
ready to permit draft writes. Both this setting and the existing connection enable
flags must be true. Nothing discovers and publishes products automatically.

The installed app must grant `write_products` and `write_files` (which include their
corresponding reads). It may retain `read_products`. Release the version and approve
the updated installation; changing the scope list alone does not grant permissions.
Each job checks the actual grants and GBP shop currency before any Shopify mutation.

Run migration `0003_shopifycatalogueproduct` to create a proxy model's admin permissions.
No existing product, stock, order or payment schema is changed.

## Review and execute

```sh
.venv/bin/python deploy/native/manage.py shopify_dry_run 7
.venv/bin/python deploy/native/manage.py shopify_sync 7 --apply
```

The first command remains strictly read-only and makes no network requests. The
second explicitly creates a durable job and executes Shopify draft writes.

Staff can instead use `/admin/system/shopify_integration/shopifycatalogueproduct/`:
select products, run the dry-run action, then explicitly select **Sync selected
products as Shopify DRAFTS**. At most 20 products may be selected per action. Grant
staff the proxy model's view permission and **Can synchronize Shopify drafts**;
no extra privileges over website checkout or payments are needed. Reviewed variant
definitions and their approvals still use the existing Phase 1 admin.

Inspect Product mappings, Sync jobs and Integration logs in the same admin. Failed
jobs contain application-owned error codes, not raw API responses or secrets.

## Dedicated background worker

Install `deploy/native/teraifoods-shopify-worker.service` as a systemd service. It
consumes only the `shopify` queue with concurrency 1 and bounded memory, leaving the
website's existing order/email worker available. Restart the scheduler to pick up
the new dispatcher: it handles only explicitly queued draft jobs, including delayed
retries. It never scans the catalogue to create jobs automatically.

## Identities, retries and non-destructive updates

- Stable Shopify handles are `teraifoods-<Django product ID>`. Website slugs remain
  unchanged. A creation-only ownership metafield identifies Django-managed products.
- Retries look up the stable identity before writing; uncertain mutations are never
  blindly replayed by the HTTP client. Missing mapped products stop for review.
- Existing products must still be drafts and have the matching ownership marker.
  Active, archived and unmanaged products are not modified.
- Known variant IDs are retained. Removing or renaming remote combinations is blocked
  for explicit review rather than implicitly deleting variants through `productSet`.
- Only managed title, handle, escaped description, options, variant prices/SKUs/weight,
  untracked inventory configuration and media associations are sent. Merchant tags,
  collections, vendor and existing metafields are omitted during updates.
- Upload filenames encode product/image identities and digest. A retry can find an
  upload whose response was lost. Ambiguous file matches stop instead of guessing.
- The retained Django JPEG rendition is used when available, even if the website
  serves AVIF. Shopify processes files asynchronously; readiness is checked.
- Existing remote media are retained. Deleting a local image does not delete remote
  media. Variant images reference their reviewed local image mapping.
- Remote prices, discounts, SKU, weights, media readiness and disabled tracking are
  verified before marking a job successful. A source change during synchronization
  leaves a retry/reconciliation job instead of an applied snapshot.
- Up to five attempts are allowed for transient failures, with exponential delays.
  Validation, ownership, permission and currency failures require staff intervention.

The integration locks only its own job/mapping rows during each attempt. A crash rolls
back local bookkeeping; subsequent attempts reconcile stable remote identities.

## Remaining approval gates

Drafts cannot be purchased. Publishing and unpublishing remain separate future
explicit operations; review product tax treatment, shipping rules and storefront
presentation before approving publication. Packages and unresolved variants remain
blocked. Shopify order import and its operational channel guards are not implemented.

References: [productSet](https://shopify.dev/docs/api/admin-graphql/latest/mutations/productSet),
[fileCreate](https://shopify.dev/docs/api/admin-graphql/latest/mutations/fileCreate).

## Deployment verification — 2026-10-30

- 109 mocked integration and existing checkout/payment/catalogue tests passed on
  isolated PostgreSQL, including Shopify's `null` representation of an empty SKU.
- Migration `0003_shopifycatalogueproduct` was applied; the dedicated worker and
  existing web, order worker and scheduler services are active.
- Pilot Django product #7 was created as draft
  `gid://shopify/Product/16208058515790`, then synchronized repeatedly without creating
  another product, variant or image. Its price (£1.99), image readiness, 150 g source
  weight and disabled inventory tracking were read back and verified.
- A real background job on the dedicated `shopify` queue completed successfully.
- Health, homepage, shop, checkout and login returned HTTP 200.
- Verification explicitly blocked writes to primary catalogue/order/customer/auth
  tables. No product was published and no order imported.
- An initial pilot verification flagged Shopify's empty-SKU/null representation;
  its failed job remains in the audit history. The compatibility fix and successful
  reconciliation reused that existing draft.
- Backups and deployment records are under
  `/opt/teraifoods/backups/shopify-phase2-20261030/`. Environment backups are private.

The Phase 2 source changes remain in the local working tree and were deployed
directly. Commit/push the integration changes through the normal repository workflow;
the server's matching manual deployment changes must be reconciled before the next
pull, preserving its unrelated product-management/AVIF files.
