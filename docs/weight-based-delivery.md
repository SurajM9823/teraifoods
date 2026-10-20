# UK weight-based delivery

The product editor at `/admin/products/` has shipping weight and unit fields.
Units are gm (`g` in the API/database) or kg. Each sellable unit defaults to
150 gm. Catalog migration 0008 backfills existing products with 150 gm without
changing prices or stock. Administrators should correct weights where needed.

At `/admin/delivery/`, add the actual delivery prices and inclusive upper weight
limits. A band may be entered in gm or kg; the database stores grams.
The smallest active band covering the basket's combined weight is selected.
For example, two 150 gm products have a shipping weight of 300 gm.
This includes the quantity of every selected product.

Coverage is the whole United Kingdom (`GB`, with `UK` accepted as an alias).
There is no distance radius or postcode surcharge. The delivery estimate defaults
to 2–4 days and can be changed on the same admin page.

No prices are seeded because the merchant has not supplied them. If the basket
exceeds every active band, or no bands exist, checkout reports that delivery is
unavailable. It never silently assumes free delivery.

The basket quote and order reservation calculate weight and charges from database
products. Client-supplied prices, weights, discounts, and shipping fees are ignored.
Order lines retain their unit weight; the order retains its total weight, delivery
charge and estimate. Later product or band edits do not change those snapshots.
Older orders retain unknown weight/charge snapshots rather than fabricated values.

Customer templates and styles are reused. Only the existing delivery amount,
estimate and total text is updated.

## Activation and verification

1. With the normal PostgreSQL database reachable, run
   `.venv\Scripts\python manage.py migrate --noinput`.
2. Add real weight-band prices at `/admin/delivery/`.
3. Check product weights and confirmed stock before accepting orders.

Delivery staff require `delivery.view_weightband`, plus
`delivery.add_weightband` / `delivery.change_weightband` for band changes and
`delivery.change_deliverypolicy` for estimate changes. Superusers have these.

Run isolated checks:

```powershell
.venv\Scripts\python manage.py test delivery catalog.test_products --settings=config.settings.test --noinput
```

Normal PostgreSQL was unavailable during local verification (connection timeout).
Tests using the explicit SQLite test settings do not establish PostgreSQL
concurrency or deployment readiness.
