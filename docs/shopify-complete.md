# Shopify channel operations

Django owns catalogue data. Shopify owns its checkout, payments, financial status,
refunds, cancellations and customer-facing fulfilments. The website's checkout,
Stripe configuration, account system and stock workflow remain the website channel.

## Catalogue

Use `/admin/system/shopify_integration/shopifycatalogueproduct/` to preview and
synchronize selected products. New products start as drafts. The synchronization
action never changes publication state. Reviewed variant definitions are required
for products with options; raw source metadata is retained.

Successful synchronization enables automatic updates for that mapped product.
The dedicated Shopify worker checks mapped products every two minutes when
`SHOPIFY_AUTO_SYNC_ENABLED=true`. It queues changes to Django-managed fields only;
it does not discover new products or publish them. Inactive/invalid source products
are flagged for staff review, never automatically archived or unpublished.

Products explicitly published through this integration can subsequently receive
catalogue updates while active. Manually activated, unapproved products are blocked
for review. An explicit unpublish is not undone by later synchronization.

## Explicit publication

1. Run `shopify_channels` to list available publication IDs.
2. Configure the intended publication IDs on the Shopify connection. Normally choose
   **Online Store** only, not every available publication.
3. Synchronize the product, review prices, images, options, weights, Shopify shipping
   rules and tax treatment.
4. Select **Publish selected products**. Review the confirmation page and explicitly
   check the approval checkbox. Staff need `publish_shopify_products` permission.

Unpublish is a separate confirmed action. It removes only the configured publication
associations and never archives/deletes the product. Failures do not automatically
perform a compensating unpublish, archive or delete. Inspect the job before retrying;
activation and publication are separate Shopify operations and an uncertain network
response may leave the first operation completed.

Server commands, requiring explicit flags:

```sh
.venv/bin/python deploy/native/manage.py shopify_publication 7 --publish --apply --confirm-reviewed
.venv/bin/python deploy/native/manage.py shopify_publication 7 --unpublish --apply --confirm-reviewed
```

`SHOPIFY_PUBLICATION_ENABLED` must be true. The code performs no publication during
deployment verification. Do not publish the pilot until its business data and
shipping/tax configuration have been reviewed.

## Orders and webhooks

Endpoint: `https://teraifoods.co.uk/api/shopify/webhook/`.

```sh
.venv/bin/python deploy/native/manage.py shopify_channels --setup-webhooks
.venv/bin/python deploy/native/manage.py shopify_channels --setup-webhooks --apply
```

The first command plans subscriptions without mutation. The second adds missing
subscriptions for order creation/update/payment/cancellation, refund creation and
app uninstall. It preserves existing subscriptions and is safe to repeat.

The endpoint verifies base64 HMAC-SHA256 against the raw request body and configured
app secret before trusting it. It validates store, topic, delivery ID and size,
persists a durable receipt, and returns promptly. Receipts store only routing IDs
and a body hash, not customer addresses or the raw webhook. Duplicate deliveries
and duplicate order IDs have independent database constraints. Broker failures do
not discard acknowledged receipts. App uninstall disables the connection.

Order import requires both `SHOPIFY_ORDER_IMPORT_ENABLED=true` and the connection's
**Import orders enabled** checkbox. Activation records a starting timestamp. Orders
created before that timestamp are ignored unless explicitly requested with
`shopify_import_order <gid> --apply --allow-historical`. No historical bulk backfill
occurs automatically. Existing imported orders continue receiving updates.

Verified receipts fetch the current GraphQL order, handling paginated lines and
out-of-order deliveries. A five-minute reconciliation job uses a durable page cursor
and overlapping update windows to recover missing webhooks. A failed fetch does not
advance the cursor. Unmapped/custom/deleted variants, packages, unsupported statuses
and invalid amounts quarantine the order rather than creating a partial order.
Review quarantines under Shopify order mappings, correct the mapping, then retry.

## Operational isolation

Imported orders have `sales_channel=shopify`, `payment_method=shopify`, no Django
customer link, and no reservation deadline. Database constraints enforce this shape.
They never call website checkout, create a Stripe Payment/session, adjust or restore
stock, issue vouchers, initiate refunds, or send Django customer notifications.
Amounts are Shopify's current shop-currency amounts (GBP), not recalculated from
today's catalogue prices or Django's delivery bands. Presentment-currency snapshots
are retained. Original line prices and current quantities are preserved separately.

View them at `/admin/orders/?channel=shopify`. Their dedicated detail screen shows
Shopify financial totals and the Shopify admin link. Local fulfilment/tracking notes
are available for internal management; they do not send Shopify shipment emails or
create Shopify fulfilments. Record customer-facing shipping in Shopify. Payments,
cancellations, refunds and returns remain managed there. Website financial controls
and guest/customer order-access endpoints reject imported orders.

Raw GraphQL snapshots are encrypted with a purpose-specific key derived from Django's
secret key and purged after 90 days. Operational order data follows the existing
business retention policy. Integration logs contain safe error codes, not credentials,
addresses, card details or raw provider messages. Customer accounts are not created
or linked by matching email. Staff permissions protect imported order details.

## Permissions, configuration and deployment

Required scopes: existing `write_products`, `write_files`, plus `read_publications`,
`write_publications`, `read_orders`. Separate `write_orders`, payment-app permissions
and customer-account write access are not used. The installed app currently has
`write_orders` as well; it can be removed. Ensure protected customer data access is
available for the order fields used by the app. Historical orders beyond Shopify's
default 60-day window require appropriate `read_all_orders` access.

Feature flags default to false: `SHOPIFY_PUBLICATION_ENABLED`,
`SHOPIFY_ORDER_IMPORT_ENABLED`, `SHOPIFY_AUTO_SYNC_ENABLED`.
For secret rotation, optionally configure `SHOPIFY_WEBHOOK_PREVIOUS_SECRET` during
the transition and remove it afterward. Keep all secrets in `.env.server` only.

New migrations: catalogue `0013`, integration `0004` and `0005`. Apply all before
restarting web, order worker, scheduler and the dedicated Shopify worker. The new
integration migration depends on the order-channel migration.

The dedicated worker consumes the `shopify` queue, including publication jobs,
catalogue updates, webhook processing and reconciliation. The website order/email
worker remains separate. Scheduler jobs never publish automatically.

Verification uses mocked API responses and isolated databases. Two broader regression
failures were reproduced on the unmodified committed baseline: an existing permissive
fulfilment transition expectation and the package detail's `2 x Rice` text expectation.
Their existing behavior was not changed by this integration.

Validation on 2026-10-30: 151 integration/checkout/payment/catalogue tests passed on
isolated PostgreSQL. The new migrations, including compatibility with an older website
worker inserting an order without the new channel field, were exercised. System,
migration-consistency and whitespace checks passed. Shopify accepted the order query
with a nonexistent order ID and the publication/webhook discovery queries; no real
orders were fetched or products published during these checks. Two unrelated baseline
failures were independently reproduced from the untouched committed source.

References: [webhook verification](https://shopify.dev/docs/apps/build/webhooks/verify-deliveries),
[publication API](https://shopify.dev/docs/api/admin-graphql/latest/mutations/publishablePublish),
[order API](https://shopify.dev/docs/api/admin-graphql/latest/objects/Order).
