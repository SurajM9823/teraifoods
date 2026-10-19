> Current IP-based server deployment: see [native/README.md](native/README.md).
> The Docker/TLS instructions below describe an alternative domain deployment.

# Docker and Nginx deployment

`compose.production.yaml` runs PostgreSQL 17, a one-off migration/static collection
service, Django through Waitress, and Nginx with TLS. Only Nginx publishes host ports.
The app runs as a non-root user; Nginx mounts static files and certificates read-only.
PostgreSQL data persists in a named volume.

Nginx serves `/static/`, redirects HTTP to HTTPS, overwrites forwarding headers,
limits request size, and rate-limits admin login by source IP. Django trusts the
scheme header only in the private proxy deployment. If adding a proxy/CDN, configure
real-client-IP trust specifically for that provider. Dynamic admin pages are not
shared-cached.

## Prepare the server

Use a Linux server with Docker Engine and Compose. Point your domain's DNS at the
server and allow inbound ports 80/443. Copy the project to the server, then:

```sh
cp .env.production.example .env.production
mkdir -p deploy/certs
```

Configure `.env.production`:

- `DJANGO_SECRET_KEY`: a long random private secret.
- `POSTGRES_PASSWORD`: a separate random password.
- `NGINX_HOST`: one hostname such as `store.example.com`, without scheme or port.
- `DJANGO_ALLOWED_HOSTS`: the same hostname.
- `DJANGO_CSRF_TRUSTED_ORIGINS`: `https://store.example.com`.

Generate secrets with a local Python installation:

```sh
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Obtain a trusted TLS certificate using your provider or ACME client. Put its full
chain at `deploy/certs/fullchain.pem` and private key at `deploy/certs/privkey.pem`.
These files and `.env.production` are ignored by Git and excluded from the image.
Configure certificate renewal outside this stack and reload Nginx after renewal.
Automatic ACME issuance is not included. Production requires certificates and does
not downgrade to HTTP if they are missing.

## Deploy

Run from the project root:

```sh
docker compose --env-file .env.production -f compose.production.yaml config --quiet
docker compose --env-file .env.production -f compose.production.yaml up --build -d
docker compose --env-file .env.production -f compose.production.yaml ps
docker compose --env-file .env.production -f compose.production.yaml exec nginx nginx -t
docker compose --env-file .env.production -f compose.production.yaml exec web python manage.py createsuperuser
docker compose --env-file .env.production -f compose.production.yaml exec web python manage.py check --deploy
```

Visit `https://YOUR_DOMAIN/admin/login` and `https://YOUR_DOMAIN/health/`.
The deployment HSTS warning remains until `DJANGO_HSTS_SECONDS` is explicitly set
after confirming HTTPS works. Subdomain HSTS and preload are not enabled automatically.

PostgreSQL traffic inside the isolated Docker network does not use transport TLS.
For hosted PostgreSQL, remove the Compose host/SSL overrides and configure the
provider's host, certificates, and SSL mode appropriately.

## Update

Back up the database first. From the updated checkout:

```sh
docker compose --env-file .env.production -f compose.production.yaml build
docker compose --env-file .env.production -f compose.production.yaml run --rm init
docker compose --env-file .env.production -f compose.production.yaml up -d --force-recreate web nginx
docker compose --env-file .env.production -f compose.production.yaml exec nginx nginx -t
```

This single-server setup may briefly interrupt service during updates. Schema
migrations must remain compatible with the previous application while it is still
running. Recreate Nginx when recreating web so its upstream address is fresh.
For certificate renewal only, validate with `nginx -t`, then run
`docker compose --env-file .env.production -f compose.production.yaml exec nginx nginx -s reload`.
Use `APP_TAG` for release image tags. Reverting an image does not reverse migrations.

## Back up PostgreSQL

Linux shell commands:

```sh
mkdir -p backups
docker compose --env-file .env.production -f compose.production.yaml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backups/terai-food.dump
```

Store backups separately and privately; verify restore into a separate database.
On older Windows PowerShell, avoid binary redirection: create a backup using
`pg_dump -f /tmp/backup.dump` inside the database container, then `docker compose cp`
it to the host. `docker compose down` retains data; `down -v` deletes named volumes.
Major PostgreSQL upgrades require an explicit upgrade/export/import procedure.

## Verification limits

Both Compose files passed validation with the official standalone Docker Compose
CLI. Django route/auth/health tests passed with explicit in-memory test settings,
and browser checks covered the custom admin plus all 19 pages at desktop/mobile
widths. Clean-route cart persistence and sidebar behavior passed. Production settings
passed security checks apart from the intentional, documented HSTS warning.

Docker Engine is absent in the working environment. Application tests and browser
checks can run locally, but container builds, startup, Nginx TLS, and PostgreSQL
migrations must be verified on a Docker host. No domain, remote server, or certificate
has been supplied, and nothing has been published.

References: [Django PostgreSQL settings](https://docs.djangoproject.com/en/5.2/ref/databases/#postgresql-notes),
[official PostgreSQL image](https://hub.docker.com/_/postgres),
[Nginx image templates](https://hub.docker.com/_/nginx).
