# Categories and subcategories

Open **Admin → Categories** at `/admin/categories/`.

1. Select **Add category**, enter its name, optionally select a Font Awesome
   icon and description, choose the display order and Active status, then save.
2. Select **Add subcategory** on that category. The parent is preselected.
3. Edit a subcategory to rename it, move it to another category, change its icon,
   description, order or status. Icons are optional; select No icon to remove one.

Slugs are generated from names when omitted and stay stable when names change.
Category names are unique ignoring case. Subcategory names are unique ignoring
case within their parent, so different categories can each have a child named
“Other”. Slugs are also unique within their level/parent. The database enforces
these uniqueness rules, including simultaneous saves.

The list supports search by category name/slug or subcategory name, category
status filtering, and pagination. Subcategories are displayed under their parent.
Delete requires a confirmation page; viewing it never deletes anything. Parents
with children cannot be deleted until those children are moved or deleted.

An inactive parent hides its entire branch from the active category tree. The
children retain their individual statuses and become eligible again when the
parent is reactivated. Deactivating a child hides only that child.

## Access and storage

Superusers can use the module immediately. Other staff need the appropriate
`catalog` category/subcategory view, add, change and delete permissions. Give
category view permission to access the main page, and subcategory view permission
to see its children. Every write is permission-checked and CSRF-protected.

Categories live in PostgreSQL; they contain no images or media uploads. The
optional icons use the existing local Font Awesome Free font, with a curated
picker and preview, so no external font service or arbitrary HTML is needed.

`catalog.content.category_tree()` returns the active hierarchy used by all storefront menus. It uses shared Redis caching for five minutes with
a lock for concurrent misses. Saves/deletes rotate the cache generation after
commit, including edits through Django admin. Cache failures fall back to the
database; invalidation failure is bounded by the payload's five-minute TTL.
Direct SQL or bulk QuerySet updates must call `invalidate_categories()` after
commit because they bypass Django signals.

## Shared storefront categories

Every storefront category menu uses `catalog/storefront/menu.html`. Existing page
wrappers, menu classes, SVG artwork, spacing and submenu structure are retained.
The same partial supplies the homepage, shop/product sidebars, mobile drawer and
JavaScript-injected dropdowns. The bulk enquiry selector also uses these rows.

Migration 0003 imports the original 11 parent categories and 58 subcategories
from the union of the old menus and category labels. It merges repeated names,
corrects the breakfast spelling, preserves existing admin records and statuses,
and is safe to run again without creating duplicates. Original SVG artwork is
kept; admins can switch to a Font Awesome icon or clear both icon fields.

Active/inactive status and edits now affect all storefront menus after commit.
Legacy shop identifiers are retained internally so existing demonstration
product filters continue to work after renaming a category or slug. Products
are still demo data; subcategory links currently browse their parent product
selection until product/subcategory assignments are implemented. No product
backend is introduced by this category refactor.

## Deploy on the existing systemd server

After deploying this code:

```sh
cd /opt/teraifoods
DJANGO_ENV_FILE=/opt/teraifoods/.env.server .venv/bin/python manage.py migrate --settings=config.settings.ip_preview
DJANGO_ENV_FILE=/opt/teraifoods/.env.server .venv/bin/python manage.py collectstatic --noinput --settings=config.settings.ip_preview
systemctl restart teraifoods-web.service teraifoods-worker.service
```

Use your actual service settings module if it differs from `ip_preview`.

For local Docker:

```sh
docker compose build web
docker compose up -d --force-recreate init web worker nginx
```

Tests: `python manage.py test catalog --settings=config.settings.test`.
Optional browser check: set `RUN_CATEGORY_BROWSER_TESTS=1` and run the same command.
