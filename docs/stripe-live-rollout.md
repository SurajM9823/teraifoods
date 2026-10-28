# Stripe live rollout — prepared, not activated

## Audit and architecture

The checkout drawer/payment page uses Stripe Checkout Sessions (`ui_mode=elements`),
Payment Element, and Express Checkout Element. It is not hosted Checkout or the
embedded Checkout page product. Existing hosted Sessions can still resume through
their original URL. No UI redesign, prices, delivery rules, voucher calculations,
tax rules, or inventory algorithms were changed. The authoritative order total is
charged in GBP; Adaptive Pricing is explicitly disabled on newly created Sessions.

`orders/views.py` provides plain Django JSON endpoints (no separate DRF serializer).
`services.create_order` owns prices, delivery, vouchers, stock reservations, guest
grants and scoped checkout idempotency. `payments.py` creates/retrieves/expires
Sessions and creates/retrieves refunds. Browser success does not mark an order paid:
signed webhooks or an owner-authorized server retrieval must verify the payment.

The existing outbox (`OrderEvent`/`Notification`, Celery and Channels) persists each
transition under an order row lock. Event IDs and state checks prevent repeated
stock/state/notification creation. WebSocket transport remains at-least-once, with
versioned snapshots. Inventory is reserved at checkout, not reduced again on payment.

Previous blockers were test-only environment selection, test key checks, rejected
live events, a hard-coded false livemode in cancellation reconciliation, and test UI
labels. Payment rows now store their mode. Migration `0005_payment_stripe_mode` adds
one column, with existing rows marked `test`, matching the old test-only code. It
does not delete orders or alter financial totals. New live payments are explicitly
marked `live`. Workers skip other-mode transactions, and API paths reject them.

## Configuration

Deploy and validate first with the existing test credentials and **STRIPE_MODE=test**.
There is no default mode. An absent/invalid mode blocks Stripe checkout rather than
silently using test keys. Example files remain in test mode; actual env files were
not edited. `check --deploy` checks configuration; checkout also validates at runtime.

| Setting | Initial validation | Approved live activation |
| --- | --- | --- |
| ORDER_PAYMENT_MODE | stripe | stripe |
| STRIPE_MODE | test | live |
| ORDER_PUBLIC_ORIGIN | https://teraifoods.co.uk | https://teraifoods.co.uk |
| STRIPE_TEST_PUBLISHABLE_KEY | pk_test_… | retained securely for test tooling |
| STRIPE_TEST_SECRET_KEY | sk_test_… or rk_test_… | retained securely for test tooling |
| STRIPE_TEST_WEBHOOK_SECRET | test endpoint whsec_… | retained securely for test tooling |
| STRIPE_LIVE_PUBLISHABLE_KEY | not used | pk_live_… |
| STRIPE_LIVE_SECRET_KEY | not used | rk_live_… or sk_live_… |
| STRIPE_LIVE_WEBHOOK_SECRET | not used | live endpoint whsec_… |

Supply real values only in the protected server environment. Never paste values in
chat, shell history, Git, diagnostics or deployment logs. Prefix checks cannot prove
that keys belong to the same account. A signing secret has no test/live prefix;
select it from the correct endpoint, then verify delivery and the event livemode.
All web/worker/beat processes must use the same selected mode.

## Restricted API key and Stripe Dashboard

Actual server calls requiring permissions:

| API resource | Operations |
| --- | --- |
| Checkout Sessions | create, retrieve, expire (read/write) |
| Refunds | create, retrieve (read/write) |

Configure permissions for these operations in Stripe's restricted-key editor,
including any dependencies it requires for inline `price_data`/`product_data`,
payment creation and refunds. Do not assume read-only access suffices. If the
Dashboard groups refund creation under Charges, include that required write scope.
Confirm the exact effective scopes and any account/IP restrictions in Workbench;
the supplied key's actual permissions are **not yet verified**. There are no direct
Customer, PaymentIntent, Product or Price API calls in this code. Do not grant broad
permissions speculatively. Test the same restricted permission set in test mode
before approval; after approval verify the live account's calls. Permission errors
return a sanitized 503, preserve guest access, and retain the same retry identity.

The existing live Snapshot endpoint must remain:
`https://teraifoods.co.uk/api/orders/webhook/stripe/`.
Confirm these seven subscriptions and a payload version compatible with the pinned
Stripe Python SDK 15.6.1:

- checkout.session.completed
- checkout.session.async_payment_succeeded
- checkout.session.async_payment_failed
- checkout.session.expired
- refund.created
- refund.updated
- refund.failed

Raw-body signature verification and a 300-second timestamp tolerance are retained.
Only this webhook is CSRF-exempt. Wrong signatures/modes return 400. Paid events
must match order, Session, amount in pence, GBP currency, and PaymentIntent. Unpaid
completion waits for an asynchronous result. Invalid events are not recorded as
processed. Monitor non-2xx deliveries and retry after repairing their cause.

Refund webhooks can bind by existing provider ID, application metadata before the
API response is persisted, or paid intent for a Dashboard refund. A refund arriving
before its payment is known receives a non-2xx response so Stripe retries. Pending
snapshots cannot undo success/failure; a reported bank failure can replace an earlier
success and restores the order's paid state. Failed refunds need staff intervention;
they are not automatically recreated with a new idempotency key.

**Existing schema limit:** one Refund per order is retained. One partial refund is
supported and leaves payment_status=paid with refund_status=partially_refunded. A full
refund marks the payment/order refunded. Repeated partial refunds, topping up a
partial refund during later cancellation/return, or creating a replacement after a
failed refund require an explicit workflow extension/manual reconciliation. Do not
create a second Dashboard refund and assume this schema can aggregate it. Conflicting
refund IDs/amounts are rejected rather than silently overwriting the first refund.
Stripe also enforces the remaining refundable balance.

## Apple Pay / Google Pay / cards

The existing Express Checkout Element remains automatic: no forced wallet buttons
or separate wallet processor. Enable card payments (including Visa/Mastercard) and
applicable wallets in live payment-method settings. Register **both**
`teraifoods.co.uk` and `www.teraifoods.co.uk` in live Payment method domains because
the server currently serves HTTPS on www without an apex redirect. Confirm test
domain registration as well. Use eligible browsers/devices with configured wallets.
Stripe performs Apple Pay merchant validation; a separate Apple Merchant ID is not
needed for this integration. HTTPS is present, but Dashboard registration and actual
device wallet rendering are unverified. Preserve Stripe frame/script/connect access
if adding a CSP later. The asset version is bumped so cached JS loses its test label.

References checked 2026-10-28:
[Express Checkout](https://docs.stripe.com/elements/express-checkout-element/accept-a-payment),
[domain registration](https://docs.stripe.com/payments/payment-methods/pmd-registration?dashboard-or-api=dashboard),
[restricted keys](https://docs.stripe.com/keys/restricted-api-keys),
[refund API](https://docs.stripe.com/api/refunds/create).

## Production findings (server AI report supplied by owner, 2026-10-28 UTC)

- `/opt/teraifoods`, systemd/Uvicorn, Python 3.12.3, Stripe 15.6.1;
  `config.settings.production`; `.env.server` loaded by `deploy/native/manage.py`.
- Commit `ba6f16bb3aba58fa67bb4d14f5ec614272f66f58`, matching the local baseline.
- Preserve modified `docs/product-management.md` and untracked
  `catalog/management/commands/convert_product_images_avif.py`,
  `catalog/test_avif_conversion.py`. Do not reset/clean the working tree.
- Web, worker, PostgreSQL 16, Redis and Nginx running. **Celery beat is absent**;
  install the existing scheduler service before relying on periodic recovery.
- STRIPE_MODE unset; test keys present; all three live variables missing.
- 57 migrations applied; latest orders migration 0004; stripe_mode column absent.
- No pending Stripe orders, requested cancellations or pending/requires_action
  refunds at report time. Recheck immediately before switching mode.
- Deploy checks: only security.W004 (HSTS unset). Do not change HSTS in this rollout.
- Backup successful 2026-10-28 02:15:41 UTC; documented isolated restore 2026-10-19.
- Both hostnames have valid TLS (expiry 2027-01-17). No CSP observed in the reported
  pages. Dashboard checks were not included in the supplied report.

Independent public checks during this task: /health/ 200, webhook GET 405, unsigned
webhook POST 400. This proves reachability/rejection, **not valid live delivery**.

## Deployment commands — prepared only, not executed

Use a reviewed release containing only the listed payment changes. Preserve server
local edits; do not use `git reset --hard`, `git clean` or a destructive sync. Upload
the reviewed changes using the established release mechanism. No dependency change
is required. First stage the code and validate in **test** mode.

```sh
cd /opt/teraifoods
git status --short
sudo systemctl start teraifoods-backup.service
sudo systemctl is-failed teraifoods-backup.service  # expected: inactive, not failed
# In the protected editor, add STRIPE_MODE=test; keep existing test keys.
sudoedit /opt/teraifoods/.env.server

# Upload the reviewed stripe-live-rollout.patch to /tmp first. Verify its supplied
# SHA256 and review its paths. These commands preserve unrelated server edits:
sudo git apply --check /tmp/stripe-live-rollout.patch
sudo git apply /tmp/stripe-live-rollout.patch

# After reviewed code is staged; reads only:
sudo .venv/bin/python deploy/native/manage.py check --deploy
sudo .venv/bin/python deploy/native/manage.py showmigrations orders --plan
sudo .venv/bin/python deploy/native/manage.py migrate --plan
sudo .venv/bin/python deploy/native/manage.py makemigrations --check --dry-run

# First run the focused mocked tests on an isolated PostgreSQL staging/test DB.
# Do not point a Django test runner at production credentials.
# .venv/bin/python manage.py test orders.test_live_payments orders.test_embedded \
#   orders.test_websockets orders.test_concurrency --settings=config.settings.test_postgres --noinput

# Scheduled maintenance window: avoid old processes writing during schema change.
# Nginx may briefly return 502; Stripe retries webhook deliveries.
sudo systemctl stop teraifoods-web.service teraifoods-worker.service
# Stop teraifoods-beat as well on later releases if it has been installed.
sudo .venv/bin/python deploy/native/manage.py migrate --noinput
sudo .venv/bin/python deploy/native/manage.py collectstatic --noinput
sudo .venv/bin/python deploy/native/manage.py check_stripe
sudo install -m 644 deploy/native/teraifoods-beat.service /etc/systemd/system/teraifoods-beat.service
sudo systemctl daemon-reload
sudo systemctl restart teraifoods-web.service teraifoods-worker.service
sudo systemctl enable --now teraifoods-beat.service
sudo systemctl is-active teraifoods-web teraifoods-worker teraifoods-beat postgresql@16-main redis-server nginx
sudo nginx -t
curl --fail --max-time 15 https://teraifoods.co.uk/health/
curl --silent --output /dev/null --write-out '%{http_code}\n' \
  -H 'Content-Type: application/json' --data '{}' \
  https://teraifoods.co.uk/api/orders/webhook/stripe/  # expected 400
sudo .venv/bin/python deploy/native/manage.py check_orders
```

Verify guest/authenticated test checkout, declines, 3DS, asynchronous events,
cancellation/refund webhooks, tracking and outbox recovery. Verify no test reservations
or pending refunds remain before cutover; changing mode intentionally stops other-mode
workers/events and must not strand stock reservations. Keep historical test records.

### Approval gate: STOP before live activation

Only after the owner explicitly approves live activation, after all blockers are
resolved, and within the agreed deployment window:

```sh
cd /opt/teraifoods
# Securely provision all three STRIPE_LIVE_* values, then STRIPE_MODE=live.
sudoedit /opt/teraifoods/.env.server
sudo .venv/bin/python deploy/native/manage.py check --deploy
sudo .venv/bin/python deploy/native/manage.py check_stripe
sudo systemctl restart teraifoods-web teraifoods-worker teraifoods-beat
sudo systemctl is-active teraifoods-web teraifoods-worker teraifoods-beat
curl --fail --max-time 15 https://teraifoods.co.uk/health/
```

Do not run a payment automatically as part of deployment. Obtain the authorized
purchase amount/order and refund scope, then have the owner use their own payment
details in Stripe's fields. Verify the exact GBP amount, live Session and intent,
HTTP 200 signed webhook delivery, one Paid/Placed transition, stock reserved once,
tracking/WebSocket/email notification, and the authorized refund's final outcome.
Verify Apple Pay on an eligible Apple device and Google Pay on an eligible configured
browser/device. Neither wallet can be established as working by mocked tests alone.

Rollback: preserve the additive column and all transaction rows. After any live
payments exist, do not simply switch the whole service to test mode: that would stop
live webhook/refund reconciliation. Pause new checkout at the edge while keeping
live webhook/worker recovery available and investigate. Do not revert to the old
test-only application once it would strand live transactions.

## Automated verification

Mocked tests run with `config.settings.test`, an in-memory SQLite database and
in-memory Channels/cache. No real charges, refunds or Stripe API calls were made.

- Focused live/configuration, embedded checkout and WebSocket tests: 31 passed.
- Final broader orders suite: 77 discovered; 64 passed, 11 skipped, 2 pre-existing
  failures. The two failures were reproduced
  with the original HEAD services module: unrestricted delivered transition versus
  the old test expectation, and missing `2 x Rice` product-detail template text.
  Business rules/UI were not changed to make those unrelated tests pass.
- `manage.py check --settings=config.settings.test`: passed.
- `makemigrations --check --dry-run --settings=config.settings.test`: no drift.
- `git diff --check`: passed.
- PostgreSQL locking tests/browser tests require their optional environments; local
  Docker daemon and PostgreSQL were unavailable. Run on isolated staging before release.
- Production env/migration/service findings above are owner-supplied diagnostics;
  no server configuration, database migration or deployment was performed here.

Remaining gates: resolve/review the existing suite failures, PostgreSQL concurrency
verification, install beat, supply live secrets securely, confirm restricted scopes,
Dashboard settings/domains, explicit activation approval, authorized live payment/
refund and eligible-device wallet checks.

## Changed files

| Files | Reason |
| --- | --- |
| config/settings/orders.py; .env.example; .env.production.example | Explicit mode and matching credential selection; test-first examples |
| orders/stripe_config.py; orders/checks.py; orders/apps.py | Runtime and deploy validation without credential disclosure |
| orders/models.py; orders/migrations/0005_payment_stripe_mode.py | Persist mode, label historical records test |
| orders/payments.py | Mode-safe Sessions, webhook validation/idempotency, refund state and balance checks |
| orders/services.py | Stamp new payments; prevent double settlement after an existing refund |
| orders/tasks.py | Recover requires_action refunds and isolate workers by mode |
| orders/views.py | Report the actual transaction mode |
| orders/management/commands/check_orders.py; check_stripe.py | Sanitized local diagnostics and other-mode backlog counts |
| web/static/web/js/stripe-payment.js; catalog/templates/catalog/storefront/assets.html | Correct live/test wording and invalidate the old JS cache |
| config/settings/test.py; orders/test_live_payments.py; orders/tests.py; orders/test_concurrency.py | Mocked test configuration, realistic refund responses, live/regression/concurrency coverage |
| docs/stripe-live-rollout.md; docs/embedded-stripe-checkout.md | Audit, checks, limitations, server-specific commands and approval gate |
