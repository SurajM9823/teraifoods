# Embedded Stripe checkout

> The rollout configuration and validation below describe the original test-only
> release. For the current explicit test/live configuration, migration, production
> findings and activation gate, use [Stripe live rollout](stripe-live-rollout.md).

## Inspection and implementation

The existing flow is `terai-interactive.js` (cart/address/payment panes),
`orders.js` (checkout request), `orders/views.py`, `orders/services.py`
(authoritative pricing, delivery, vouchers and inventory reservation), and
`orders/payments.py` (Stripe Checkout Sessions and signed webhook processing).
`catalog.Order`, `orders.Payment`, `CheckoutAttempt` and `ProviderEvent` already
hold the required references and idempotency records. No database migration is
needed. Refunds and existing hosted Checkout orders remain supported.

New Stripe Sessions use `ui_mode=elements` with the existing pinned Stripe SDK.
`stripe-payment.js` mounts Payment Element and eligible Express Checkout buttons
inside the existing payment panel, using the site's purple colour and square
inputs. The order summary and delivery calculation remain server-owned. New
payments don't navigate to hosted Checkout; bank authentication or another
redirect-based payment method can still require an external authentication step.

The new owner-authorized POST endpoints are:

- `/api/orders/<order UUID>/payment/`: resume payment and return the short-lived
  client secret with a publishable test key (responses are never cached).
- `/api/orders/<order UUID>/payment-status/`: retrieve Stripe status server-side.

The browser never marks an order paid. Signed Checkout Session webhook events
and server retrieval use the existing amount/currency checks and idempotent
event processing. Unpaid sessions are reused, and changing checkout details
expires/cancels the previous unpaid session before reserving a replacement.
Asynchronous processing cannot release inventory before its result is known.
Provider outages preserve guest session identity even on a 503 response.

## Remembering delivery details

`orders.Address` and `/api/orders/addresses/` remain the account address book.
Selection, explicit saving/updating, deletion, default restoration and duplicate
prevention use the authenticated account, never an email supplied by the browser.

Guests can opt into remembering delivery details for 30 days, using the existing
`teraifood_uk_address` local-storage key. Only whitelisted delivery/contact fields
are saved. Session contact data is scoped to guest/account identity. Clearing
checkout details removes browser copies; account addresses have their own Delete
control. Signing in does not silently merge a guest address into the account.

Saved cards are deliberately not offered. There is no Stripe Customer lookup by
email, no `setup_future_usage`, no save-card checkbox, and Elements' save/redisplay
options are disabled. Card/CVC fields belong to Stripe iframes. Secret keys and
client secrets are never stored in browser storage or application payment rows.

## Configuration — manual steps before real Stripe testing

1. In the **same Stripe test environment** as your secret key, open **Developers /
   API keys** and copy the **publishable key** (`pk_test_...`). Add this new line
   to the environment of the server where you will test:

   ```dotenv
   STRIPE_TEST_PUBLISHABLE_KEY=your_full_pk_test_key
   ```

2. Keep the existing real values for `STRIPE_TEST_SECRET_KEY`,
   `STRIPE_TEST_WEBHOOK_SECRET`, and `ORDER_PAYMENT_MODE=stripe`. Do not paste
   secret keys into chat, source files, or Git. No `.env` was changed by this task.

3. Set `ORDER_PUBLIC_ORIGIN` to the server actually running this checkout:
   `http://127.0.0.1:8080` for local Docker, or `https://teraifoods.co.uk` for the
   deployed site. Updating local `.env` does not configure the production server.

4. The webhook endpoint is unchanged:
   `https://teraifoods.co.uk/api/orders/webhook/stripe/`. Use snapshot events in
   the test environment: `checkout.session.completed`,
   `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`,
   `checkout.session.expired`, `refund.created`, `refund.updated`, `refund.failed`.
   For local testing run `stripe listen --forward-to
   http://127.0.0.1:8080/api/orders/webhook/stripe/` and use that listener's `whsec_`
   locally. The public endpoint and CLI listener have different signing secrets.

5. In Stripe payment-method settings, enable methods appropriate for the business.
   Register the exact HTTPS website domain under **Payment method domains** for
   Apple Pay/Google Pay and other domain-dependent methods. Stripe determines
   availability by account configuration, device, currency and transaction.
   Don't expect every wallet on localhost or on every device. If your production
   reverse proxy sets CSP, allow Stripe.js, Stripe frames and Stripe connections
   according to Stripe's current security guidance; don't disable CSP globally.

6. After reviewing these changes, deploy through your normal release procedure.
   No deployment or production database operation was performed for this task.
   Recreate application processes to load environment changes. For the local
   Docker setup, after you choose to apply the change:

   ```powershell
   docker compose build web
   docker compose up -d --no-build
   docker compose exec -T nginx nginx -s reload
   ```

7. Test a real checkout with Stripe test card `4242 4242 4242 4242`, a future
   expiry and any three-digit CVC. Test declines (`4000 0000 0000 9995`), 3DS
   (`4000 0025 0000 3155`), closing/reopening payment, duplicate clicks, refreshing,
   guest/account addresses and cancellation. Confirm webhook delivery returns
   HTTP 200 and the server order changes to Paid/Placed. Never use a real card
   or live-mode key for this test-only integration.

## Verification limits

Local `.env` has no usable test secret/publishable/webhook keys. Automated tests
use Stripe SDK mocks and a browser-only Stripe Element double. They verify the
application integration, decline/retry UI, amount checks, signature verification,
idempotency and address storage, but cannot prove real Stripe iframe rendering,
bank authentication or device-specific wallets. The dashboard/key steps and real
test transactions above remain necessary before release.

References: https://docs.stripe.com/payments/quickstart,
https://docs.stripe.com/js/custom_checkout/init,
https://docs.stripe.com/js/custom_checkout/confirm,
https://docs.stripe.com/payments/payment-methods/pmd-registration,
https://docs.stripe.com/testing.
