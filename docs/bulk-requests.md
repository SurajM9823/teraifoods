# Bulk requests

The existing `/bulk-order/` spreadsheet-style page now submits to a persistent
database workflow. Sample buyers, sample line items, generated success references,
automatic 5% discounts and claims of an emailed PDF were removed. Product search
uses the catalog; off-catalog requirements remain supported. Customer-entered unit
prices are target prices, not an approved quote.

## Customer

Enter company, contact, email, UK phone, delivery address/postcode, optional date
and notes, plus up to 100 item lines. Submission creates a `TF-BQ-` reference.
Retries with the same submission key do not duplicate a request. The same page's
**My Bulk Requests** section shows details, status, quote, delivery/payment terms
and response history. It refreshes every 15 seconds while visible and has a manual
refresh control. Signed-in users see their own requests; guests use their session
or the signed 30-day email link. A reference or email address alone does not grant
access. Tracking endpoints return private, non-cacheable responses.

## Staff

Use `/admin/bulk-orders/` (the existing Bulk Order Inquiries navigation link).
Search by reference/company/contact/email and filter by status. Open the request
to see all submitted information and send a response. Quotes require a non-negative
GBP total, delivery terms and payment terms; include item-level breakdowns in the
response. Status progresses through review, quoted, accepted, processing,
dispatched and completed, with rejection/cancellation branches. Staff must record
customer acceptance before processing; no customer acceptance is inferred.

Every response records the acting staff member, status, quote snapshot and time.
Stale admin submissions are rejected to avoid overwriting another response.
`orders.view_bulkrequest` and `orders.change_bulkrequest` control access; superusers
already have these permissions. Read-only staff cannot respond.

Customer emails use the existing worker/30-second recovery scheduler and contain
the secure tracking link. The admin history displays email delivery status.
SMTP retries use stable Message-IDs, but SMTP cannot guarantee exactly-once
delivery across crashes. Local email is available in Mailpit at port 8025.

Bulk requests do not reserve stock, charge cards, generate invoices or create
retail orders automatically. The admin quote establishes the commercial terms.

## Checks and deployment

```powershell
docker compose build web
docker compose up -d --no-build
docker compose exec web python manage.py migrate --noinput
docker compose exec nginx nginx -s reload
.venv\Scripts\python manage.py test orders.test_bulk --settings=config.settings.test --noinput
$env:RUN_ORDER_BROWSER_TESTS='1'
.venv\Scripts\python manage.py test orders.test_browser.OrderBrowserTests.test_bulk_request_admin_response_and_tracking --settings=config.settings.test --noinput
```

Tests cover validation, idempotency, ownership/guest links, permissions, quote
requirements, state transitions, history, email deduplication and a real browser
submission followed by an admin quote visible on the customer page.
