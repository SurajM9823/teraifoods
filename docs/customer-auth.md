# Customer accounts

Customer authentication uses Django sessions, django-allauth, PostgreSQL, Redis,
Celery and SMTP. The old browser-only login/Google/OTP simulation and stored PIN
have been removed. Existing browser demo accounts were never real accounts: sign
up again. No password or reusable PIN is sent by email. Use a strong password
(12 characters minimum), a six-digit email sign-in code, or Google.

## Try it locally

Keep Docker Desktop running, then run `docker compose up -d`.

- Sign up: http://localhost:8080/accounts/signup/
- Sign in: http://localhost:8080/accounts/login/
- Reset password: http://localhost:8080/accounts/password/reset/
- Account settings: http://localhost:8080/manage-profile/
- Local email inbox: http://localhost:8025/

Until real SMTP credentials are configured, Mailpit captures emails locally.
Enter any valid test email, open the local inbox, and copy the newly generated
six-digit code. It is not shown in the storefront or hardcoded. Mailpit does not
deliver to Gmail or another real mailbox. It binds only to localhost and is not
included in production Compose. Messages disappear when its container is recreated.
Codes expire after 10 minutes, allow three incorrect attempts, and are tied to
the requesting browser session. Request a fresh code if the session expires.

## Gmail or another SMTP provider

Edit your existing `.env` without replacing other settings:

```dotenv
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-address@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
DEFAULT_FROM_EMAIL=Terai Food <your-address@gmail.com>
```

Then run `docker compose up -d --force-recreate web worker`.
Use a provider app password, not your normal mailbox password. Never commit these
values or paste them into chat. For another provider use its SMTP host/port and
verified sender. TLS and SSL must not both be enabled. SMTP delivery has bounded
timeouts and up to three retries. Check `docker compose logs --tail=50 worker`
for delivery failures; credentials and OTP contents are not intentionally logged.

## Continue with Google

In Google Cloud create a Web application OAuth client, configure its consent
screen and test users while it is in Testing mode, and enable the email/profile
scopes. Add the exact authorized redirect URI:

```text
http://localhost:8080/accounts/google/login/callback/
```

If you use `127.0.0.1` instead, also register
`http://127.0.0.1:8080/accounts/google/login/callback/`. Use HTTPS and your actual
domain in production. In `.env` set:

```dotenv
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
```

Restart web and worker as above. The Google button becomes available only when
both values exist. An SMTP app password does not enable Google sign-in.
OAuth uses state validation and PKCE; initiation is CSRF-protected POST. Google
tokens are not retained. A verified existing customer may use an authoritative
Google Gmail/Workspace identity with the same email; staff accounts and other
email-provider addresses must sign in first and explicitly connect Google under
Account settings. Never link an unverified local account merely by email match.

Live Google consent and live SMTP delivery require your credentials and must be
checked after setup; automated tests mock Google's external response, not the
application's state/session/redirect handling.

## Security and operations

- Django ORM queries bind parameters; authentication does not build SQL from
  submitted input. Django validates passwords, hashes them, checks CSRF, and
  rotates sessions. Password reset invalidates existing password-based sessions.
- The database indexes email lookups on both the user and allauth email tables;
  allauth enforces unique verified emails. Existing users are preserved.
- Mandatory email verification, generic account-existence responses, bounded
  code attempts and resend cooldowns protect recovery and signup flows.
- Shared Redis limits cover account and IP attempts. An additional atomic IP
  counter bounds all account POST requests. Redis failures block authentication
  with 503 rather than bypass limits. Redis is private and capped at 128 MB with
  no eviction. A restart clears rate limits and queued messages; users can request
  another code. Database sessions remain intact.
- Nginx adds request/connection limits, small auth request bodies and timeouts.
  It overwrites proxy headers; Waitress accepts one proxy hop. Do not expose the
  web container directly or accept arbitrary client-supplied proxy headers.
- Celery receives encrypted email payloads, only accepts JSON and does not store
  task results. Queued emails expire after five minutes; OTPs are never written
  to browser localStorage. Treat database/Redis backups as sensitive regardless.
- Production uses secure cookies and HTTPS. SMTP and Google require outbound
  access, so web and worker join the egress network without publishing ports.
- Local request limiting is not protection against bandwidth-saturating or
  distributed attacks. Public deployment still needs a provider/CDN WAF and DDoS
  protection, monitoring, capacity testing, and maintained dependencies. Configure
  trusted proxy IP handling explicitly before placing a CDN in front of Nginx.

Run `docker compose exec web python manage.py test customers` for PostgreSQL
authentication tests. Fast isolated tests use
`.venv\Scripts\python manage.py test --settings=config.settings.test`.

The customer account page now exposes real account security settings. The old
demo address/payment/profile editor is no longer served; commerce remains outside
this authentication implementation.

References: [allauth settings](https://docs.allauth.org/en/latest/account/configuration.html),
[Google provider](https://docs.allauth.org/en/latest/socialaccount/providers/google.html),
[Celery with Django](https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html).
