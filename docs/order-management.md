# Ordering implementation and local operation

## Prompt audit

The original product catalog, database inventory audit, local-storage cart,
storefront styles, category administration, and postcode/map integration were
reused. The original payment, order tracking, and order-admin screens contained
demonstration data. They are now connected to the order backend.

| Flow | Implementation |
| --- | --- |
| Product details, cart, wishlist | Database product payloads; persistent browser basket/wishlist; authoritative checkout prices and stock. Detail and lazy-loaded card wishlist controls work. |
| Delivery | Whole UK, gm/kg per product, default 150 gm, inclusive weight bands, admin-configured 2–4 day default estimate, immutable order snapshots. |
| Guest checkout | No registration requirement; contact/address collection, session-scoped idempotency, signed expiring email tracking links. |
| Payments | Local demo confirmation is available; Stripe hosted Checkout adapter, signed webhooks, reconciliation and refunds are implemented and tested with mocked provider responses. Actual Stripe credentials/connection were explicitly deferred by the owner. |
| Tracking | Authenticated/guest session authorization, origin checks, Redis/Channels WebSockets, version deduplication, reconnect/backoff, heartbeat and HTTP recovery. Status tracking and administrator-entered HTTPS courier links; no fabricated GPS. |
| Notifications | Durable database event/outbox, Celery worker, periodic recovery, email status/attempt timestamps, account notifications, explicit opt-in browser notifications while the page is open. |
| Administration | Real order list/search/status filters/pagination; controlled transitions, assignment, courier link, history, customer-support replies, cancellation, return decisions and refunds. |
| Handover | Recipient-only encrypted email PIN, hashed verification, expiry, five-attempt lockout, audit, assigned-driver endpoint. Alternative proof requires policy to permit it. |
| Saved addresses | Owner-only CRUD/default address, selection at checkout, full historical order-address snapshots. Postcodes.io is reused for postcode-area lookup; manual entry remains available. |
| Reviews | Delivered-purchase eligibility, registered and verified guest access, one review per order line, validated/optimized images, moderation, approved ratings/counts, report flag and pending-photo deletion API. |

Customer CSS was not redesigned. Existing page layouts/classes and controls were
reused; missing contact fields, genuine data, and necessary action controls were
added. Page screenshots are in `scratch/orders-baseline/` and
`scratch/orders-after/`. These folders are local verification artifacts.

## Local Docker demo

Local Compose defaults to `ORDER_PAYMENT_MODE=demo`. This also requires `DEBUG`.
It cannot confirm demo payments when `DEBUG=False`. The payment page explicitly
states that no card or money is involved; this is a local simulation, **not a
transaction against Stripe's sandbox**. Demo orders have `payment_method=demo`.
Demo refunds never contact Stripe.

```powershell
docker compose build web
docker compose up -d --no-build
docker compose exec web python manage.py migrate --noinput
docker compose exec web python manage.py seed_demo_delivery
docker compose exec web python manage.py seed_demo_inventory
docker compose exec nginx nginx -s reload
docker compose exec web python manage.py check_orders
```

Sample inventory is only added to published products with unconfirmed stock,
with an inventory audit explaining that it is local demonstration stock. Existing
confirmed inventory and existing delivery bands are preserved. The sample rates
are £2.99 up to 500 gm, £3.99 up to 1 kg, £5.49 up to 2 kg, £7.99 up to 5 kg,
£11.99 up to 10 kg, and £17.99 up to 20 kg. These are not production prices.

- Store: `http://127.0.0.1:8080/`
- Orders: `http://127.0.0.1:8080/admin/orders/`
- Delivery rates: `http://127.0.0.1:8080/admin/delivery/`
- Review moderation: `http://127.0.0.1:8080/admin/orders/reviews/`
- Local email/PIN inbox: `http://127.0.0.1:8025/`

Create an optional sample order through the real order service:

```powershell
docker compose exec web python manage.py create_demo_order --confirm
```

It uses `demo@example.invalid` and a clearly marked "do not dispatch" address.
For manual recovery and diagnostics:

```powershell
docker compose exec web python manage.py process_orders
docker compose logs --tail=50 web worker beat
```

Run exactly one beat scheduler per environment. Native deployment includes
`deploy/native/teraifoods-beat.service`; the web service now runs ASGI, and Nginx
needs the `/ws/` upgrade configuration. Production files were prepared, not
deployed to a remote server during this task.

## Stripe connection later

Set `ORDER_PAYMENT_MODE=stripe`, `STRIPE_TEST_SECRET_KEY`,
`STRIPE_TEST_WEBHOOK_SECRET`, and the correct `ORDER_PUBLIC_ORIGIN` locally.
Restart web/worker/beat after environment changes. Forward Stripe test webhooks
to `/api/orders/webhook/stripe/`. The adapter accepts test-mode keys only.
Browser success redirects never mark an order paid; signed webhooks do.

References used for the integration:
[Stripe Python SDK](https://github.com/stripe/stripe-python),
[Checkout Sessions](https://docs.stripe.com/api/checkout/sessions/create),
[Channels origin security](https://channels.readthedocs.io/en/stable/topics/security.html).

## Business settings and limits

### Delivered returns and refund records

Customers request a return from the delivered order and select original payment,
an issued voucher, or UK bank transfer. Bank transfers require account holder,
sort code and account number; these are encrypted at rest, excluded from customer
API/WebSocket/event payloads, and removed after manual settlement. Staff with order
change permission can view them on the order detail page while handling the return.

Use `/admin/orders/?returns=1` to find return requests. Approve/reject first, then
record receipt and explicitly select whether stock is suitable for resale. Bank
and voucher requests wait for manual settlement; the background Stripe refund
worker cannot process them. For original-payment requests, select manual handling
at receipt if an alternative payment method has been agreed with the customer.

After actually making the payment or issuing a voucher, record the method and
payment reference / voucher code in **Record completed refund**. This supports
bank, voucher, cash and other methods, records the administrator and timestamp,
notifies the customer, and shows the reference on their authorized tracking page.
It does not execute a bank transfer or create/redeem a store checkout voucher;
the code must identify a voucher already issued by the store. A pending provider
refund cannot also be settled manually, preventing duplicate payouts.

Verified purchase reviews remain available after delivery, including when an item
is returned. One review per purchased order line is accepted, and approval at
`/admin/orders/reviews/` is required before it contributes to public product ratings.

- `ORDER_RETURN_DAYS=0` accepts delivered-order return requests for manual review;
  it does not promise automatic eligibility. A positive value enforces that
  configured online request window. Admin approval/receipt is required for refund.
- `ORDER_DELIVERY_PIN_REQUIRED=true` is the default. PINs expire after 24 hours.
- Monetary totals use existing GBP prices and shipping. No new VAT rate or
  promotional-code policy is invented. Product sale discounts are snapshotted.
- The browser stores no card numbers/CVC. Notifications are not background Web
  Push; an open tracking page is required for WebSocket/browser updates.
- Email uses a durable outbox and stable Message-ID. A crash after SMTP accepts
  a message but before acknowledgement can still produce a duplicate delivery.
- Postcode coordinates do not identify a front door. No driver GPS feed or
  external courier API credentials were supplied; tracking remains status-based.
- Two imported source products lack required original catalog data and remain
  drafts. Their missing information must be corrected in product administration.
- Production stock/prices/settings were not replaced with local samples.

## Verification commands

```powershell
docker compose run --rm --no-deps web python manage.py test --settings=config.settings.test_postgres --noinput
$env:RUN_ORDER_BROWSER_TESTS='1'
.venv\Scripts\python manage.py test orders.test_browser --settings=config.settings.test --noinput
.venv\Scripts\python tools/order_socket_smoke.py
```

The isolated browser tests cover real product details, wishlist persistence,
gm/kg quotes, guest address entry, both local demo and mocked Stripe checkout,
webhook confirmation, tracking and basket clearing. PostgreSQL tests cover stock
races and concurrent checkout retries. Socket tests cover guest authorization,
origin restrictions, state sync and revocation. The Compose diagnostic exercises
the actual Nginx/ASGI/Redis path and removes its temporary diagnostic order.
