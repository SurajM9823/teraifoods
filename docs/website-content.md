# Homepage content management

Open **Admin → Website content** (`/admin/cms/`). Superusers already have access.
For editors, assign the CMS view/add/change/delete banner permissions and the
view/change information block permissions in Django's Users or Groups screen.
The CMS checks permissions on every request and requires CSRF tokens on writes.

## Carousel

Both original images are **1170 × 548 pixels** (about 2.14:1). Use that size or
a larger image with the same ratio. Keep the subject on the right and the left
half uncluttered for the heading and button. The existing design crops images
on mobile (360px banner height; tablet 420px), so check narrow screens after
uploading. JPG, PNG and WebP are accepted, up to 5 MB and 24 megapixels.

Edit the badge, title, description, image, alternative text, button label,
destination, display order and published status. Smaller order numbers appear
first. Destinations must be local paths such as `/shop/`. All text is escaped.
Hide or delete a banner to remove it from the homepage.

Product linking is deliberately deferred. The old hard-coded prices were not
connected to products and have been removed. When the product model is ready,
add an optional product relation and derive price, sale price and availability
from it. Product changes must then invalidate this content cache too. Use
category/collection links for general promotions and product links only for
specific product offers; do not manually duplicate product prices in banners.

## Four information blocks

Each existing icon has one editable heading and description, with a published
toggle. These are rendered into HTML for visitors and search engines, not
loaded later by JavaScript. Their existing desktop/mobile visibility is
preserved. Seed content avoids unverified claims such as delivery within one
hour. Review the copy to match your actual payment and delivery policies.

## Cache behavior

PostgreSQL stores content; Redis holds one shared public payload for all visitors
for five minutes. A warm request makes no CMS database queries. Redis's lock
coalesces concurrent cache misses across web processes; a cold load reads two
tables. No customer identity or session data enters the payload.

Saving, hiding or deleting content rotates a generation key **after transaction
commit**. An in-flight old load can only populate the old generation, so it cannot
overwrite a newly published generation. Rollbacks do not invalidate. Django
admin changes use the same signals. Direct SQL, `QuerySet.update()` and bulk
operations bypass signals: call `invalidate_home()` on commit when using them.

If Redis is unavailable, the site reads the database. Concurrent requests may
also fall back if the lock cannot be obtained within ten seconds. If Redis fails
during invalidation, old cached data can survive for at most its five-minute TTL;
the failure is logged. Cache failures never report that a database save failed.

## Server media storage

Cloudflare R2 is deferred. Uploads always use Django's local filesystem storage;
no cloud credentials are required. Any old R2 environment variables are ignored.

Files are separated from application code and collected static assets:

```text
/opt/teraifoods/media/
??? cms/
    ??? banners/
        ??? YYYY/
            ??? MM/
                ??? unique-id.jpg
```

New uploads use the current year and month. Existing stored file paths continue
working without moving files. Every replacement gets a new filename so browsers
cannot reuse the previous image. PostgreSQL stores the paths and content, Redis
shares the content payload, and Nginx serves the images from disk. Back up both
the database and `media/`; collectstatic does not copy or back up uploaded files.
Old replaced images are retained; do not delete files still referenced by banners.

### Existing systemd server

After deploying the code, prepare the directory using the web service's user:

```sh
cd /opt/teraifoods
web_user=$(systemctl show teraifoods-web.service -p User --value)
web_user=${web_user:-root}
install -d -m 755 -o "$web_user" /opt/teraifoods/media
.venv/bin/pip install -r requirements.lock
DJANGO_ENV_FILE=/opt/teraifoods/.env.server .venv/bin/python manage.py migrate --settings=config.settings.ip_preview
DJANGO_ENV_FILE=/opt/teraifoods/.env.server .venv/bin/python manage.py collectstatic --noinput --settings=config.settings.ip_preview
systemctl restart teraifoods-web.service teraifoods-worker.service
```

Add this inside the site's existing Nginx `server` block:

```nginx
location ^~ /media/ {
    alias /opt/teraifoods/media/;
    autoindex off;
    add_header X-Content-Type-Options nosniff always;
    expires 1y;
}
```

Then run `nginx -t && systemctl reload nginx`. If the service uses
`ProtectSystem=strict`, its `ReadWritePaths` must include `/opt/teraifoods/media`.
Uploads need no changes to `.env.server`. For HTTPS production, use your actual
production settings module instead of `ip_preview` in the commands above.

The bundled starter images work immediately from static files. To optionally
copy them into media, run this as the web service user (not a different owner):

```sh
sudo -u "$web_user" env DJANGO_ENV_FILE=/opt/teraifoods/.env.server /opt/teraifoods/.venv/bin/python /opt/teraifoods/manage.py upload_cms_banners --settings=config.settings.ip_preview
```

This command skips banners that already have uploaded images. If you previously
uploaded anything to R2, download those objects into `media/` at their exact
stored paths before switching; this change cannot retrieve cloud objects.

### Local Docker

Docker uses a persistent `media_files` volume mounted at `/app/media` in the app
and `/var/www/media` in Nginx. Container recreation preserves uploads. Do not
remove this volume when rebuilding.

```sh
docker compose build web
docker compose up -d --force-recreate init web worker nginx
```

Verification: `python manage.py test cms --settings=config.settings.test`.
