# Customer accounts

## Investigating missing emails on a Linux server

The browser acknowledgement means the email was queued, not that it reached an
inbox. `customers.email` logs `email_queued`, `email_delivery_started`,
`email_smtp_accepted`, `email_delivery_retry`, and `email_delivery_failed`, correlated
by task ID. SMTP acceptance is not proof of inbox delivery. Failure logs include
the exception class and SMTP status number, but omit the provider's raw error
message, recipients, credentials and OTPs. An expired/encryption-key-mismatched
message produces `email_discarded`. Web and worker must share the same secret key.

First identify the actual deployment; installing Docker does not attach it to an
already running systemd/Supervisor app:

```sh
systemctl list-units --type=service --all | grep -Ei 'gunicorn|uvicorn|waitress|django|terai|celery|redis|supervisor'
ss -ltnp | grep -E ':(80|443|8000|8080|6379)\b'
```

For systemd, substitute the service name found above:

```sh
journalctl -u YOUR_CELERY_SERVICE -n 100 -f
```

For the supplied Docker production deployment:

```sh
docker compose --env-file .env.production -f compose.production.yaml logs --tail=100 -f web worker
```

Example files are templates and are never loaded automatically. Non-Docker runs
load `.env` by default; exported process variables take precedence. After deploying
this version, explicitly select `.env.production` with `DJANGO_ENV_FILE` in both
web and worker services. Use their same Unix user, virtualenv, environment and
settings when diagnosing. For example, from the project directory:

```sh
DJANGO_ENV_FILE=/opt/teraifoods/.env.production .venv/bin/python manage.py check_email_setup --settings=config.settings.production --smtp
```

This reports whether credentials are present without displaying them, checks the
cache, Celery broker and worker responses, and tests SMTP connection/authentication
without sending email. For a non-Docker deployment, database and Redis hostnames
must identify your real services; Docker-only names such as `db` and `redis` may
not resolve. Restart the actual web and worker services after configuration changes.
Do not enable Django DEBUG or SMTP protocol debugging on a public server.

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

Customer login and signup already use the real Google OAuth flow. To activate it:

1. In Google Cloud / Google Auth Platform, create or select your project and
   configure the consent screen for external customers (app name, support email,
   contact email, and your website details). Use email/profile identity scopes.
2. Create an OAuth client with application type **Web application**.
3. Register the exact callback URLs below. For your live site use
   `https://YOUR-DOMAIN/accounts/google/login/callback/`, including the trailing
   slash. The public server IP `http://178.105.139.193/` is not a valid production
   callback: Google requires HTTPS and a domain (localhost is the development
   exception). Do not use the homepage as the callback URL.
4. Copy the client ID and client secret into `/opt/teraifoods/.env.server` on the
   systemd server, or `.env` for local Docker. Keep the secret out of chat and Git.
5. Restart systemd services with:
   `systemctl restart teraifoods-web.service teraifoods-worker.service`.
   For Docker, use `docker compose up -d --force-recreate web worker`.
6. Open customer login, click **Continue with Google**, and complete consent.
   Verify that you reach `/manage-profile/`. Configure the consent audience for
   your customers before launch; add test accounts when required by Testing mode.

An email app password is unrelated to OAuth. JavaScript origins are not required
by this server-side redirect flow. Use the same host in the browser as the
registered callback. Configure HTTPS/allowed hosts/CSRF trusted origins for your
live domain before testing production. See Google's
[redirect URI validation rules](https://developers.google.com/identity/protocols/oauth2/web-server#uri-validation).


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
