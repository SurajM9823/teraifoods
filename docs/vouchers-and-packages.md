# Return vouchers and product packages

## Vouchers

A delivered order's customer can choose Voucher when requesting a return. Admin
approval alone does not issue credit: marking the return received creates a
random, single-use voucher and marks that return refunded. The customer receives
an email update linking to secure order details, which show the voucher code/value.
The code also appears on the admin order detail page.

Use the existing voucher/promotion input at cart or checkout. Validation requires
the original return email. The credit applies to the purchase total including
delivery. If credit is smaller, only the remainder is charged. If credit covers
the total, the order confirms without Stripe. The entire voucher is consumed on
successful payment; surplus value is forfeited and is never usable again.

Concurrent checkouts cannot reserve the same code. Failed/unpaid checkout
cancellation or expiry releases a reservation; browser redirects never redeem
credit. Payment retries keep the original order and amount. Cancelling an already
paid voucher purchase issues a replacement only for the value actually applied,
not any forfeited surplus. Cash refunds remain limited to money charged. Choosing
a voucher for a subsequent return credits its cash amount plus applied credit.
Bank/cash transfers are still carried out externally and recorded by staff.

## Packages

Manage packages at `/admin/packages/` or **Product packages** in the admin sidebar.
Select component products and per-package quantities, a percentage or fixed GBP
discount, title/subtitle/tagline, category and image. Choose banner slot 1, 2 or 3
and publish. Unpublishing restores the existing promotional artwork for that slot.
No example packages were published into real inventory.

Uploads are validated and center-cropped to **867 × 441 pixels**, matching the
existing banners. Place product artwork to the right and leave text space on the
left. Existing customer CSS, banner wrappers, spacing and responsive dimensions
are retained. The banner opens the existing product-detail page; it lists the
package contents and uses the normal basket and checkout.

Package price uses the current component selling prices and configured discount.
Weight is the sum of component weights. Availability is constrained by every
component's confirmed stock and publication state. Checkout locks component rows,
combines package and separately purchased quantities, and audits physical stock
deductions. Order lines snapshot their component quantities; cancellation/return
restocking uses those snapshots even after an administrator edits a package.
Nested packages are not allowed. Package administration requires the standard
`catalog.view_package`, `catalog.add_package`, `catalog.change_package` permissions.

## Verification / operation

```powershell
docker compose build web
docker compose up -d --no-build
docker compose exec web python manage.py migrate --noinput
docker compose exec nginx nginx -s reload
docker compose run --rm --no-deps web python manage.py test --settings=config.settings.test_postgres --noinput
$env:RUN_ORDER_BROWSER_TESTS='1'
$env:POSTGRES_HOST='127.0.0.1'
.venv\Scripts\python manage.py test orders.test_browser.OrderBrowserTests.test_package_banner_and_return_voucher_checkout --settings=config.settings.test_postgres --noinput
```

The package browser test uses isolated PostgreSQL: SQLite's shared in-memory
LiveServer connection cannot reliably handle its overlapping requests. Tests cover
automatic issuance, partial and full coverage, forfeiture, duplicate redemption,
expiry/cancellation recovery, mixed basket stock, historical restocking, package
publishing/image cropping and the complete banner-to-checkout voucher flow.
