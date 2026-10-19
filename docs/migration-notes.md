# Migration and verification notes

## Current routing and deployment update

The sections below describe the initial conversion. Public routes now use clean
trailing-slash URLs, with permanent redirects from `.html` URLs. PostgreSQL is now
the development/production database. See the root README and `deploy/README.md` for
Docker Compose and Nginx setup. SQLite is retained only for explicit offline tests
and access to the original database during account export.

The owner's subsequent Shop style edits and About-to-Shop redirect were preserved.
Inline-style regression fingerprints in `web/tests/fixtures/inline_styles.json`
reflect that current design; the original ZIP remains a historical reference.

## Preserved source

The original 19 HTML pages and all original asset files are saved in
`original-frontend.zip`. Thirteen top-level pages and six articles now render from
`web/templates/web/`. Original CSS, images, and fonts are unchanged byte-for-byte;
inline styles differ only where a local asset needs Django's static URL.

JavaScript and template URL changes support Django static paths and root-relative
navigation. Django `verbatim` protects WooCommerce/Underscore placeholders. The
shared product index was extended to recognize `.shop-product-card` and its price
markup, fixing shop buttons which otherwise could not find their product.

## Validation performed

- Django system check and initial database migrations.
- Ten Django tests: all pages, direct markup assets, CSS dependencies, local HTML
  links, route directory, unknown URLs, read-only handlers, template preservation,
  original media/style bytes, and inline-style preservation.
- Static collection for deployment.
- Headless Microsoft Edge across all 19 pages at 1440px and 390px widths: no uncaught
  JavaScript exceptions and no horizontal document overflow were observed.
- Browser cart check: first shop product added at its displayed £8.99 price,
  persisted across page navigation, and appeared in the shared cart drawer.
- Homepage mobile screenshot inspected; representative screenshots are in ignored
  `scratch/` output. No automated pixel-perfect comparison was performed.

Repeat the browser check with the Django development server running:

```powershell
node tools/browser_smoke.cjs
```

This optional helper requires Node 22+ and Microsoft Edge at its standard Windows
installation path. It uses a disposable browser profile and writes screenshots and
JSON reports under `scratch/`; it does not use an existing logged-in profile.
The browser sweep records findings; the cart interaction check controls the exit code.

## Restored dependencies

The original Leaflet CSS referred to missing `css/images` resources. Five standard
PNG assets were restored from the matching [Leaflet v1.9.4 source](https://github.com/Leaflet/Leaflet/tree/v1.9.4/dist/images).
Their license is included in `leaflet-license.txt`. Legacy icon-font SVG paths now
resolve through copies of the existing supplied SVGs under `static/web/font/`.
No CSS edits or substitute product artwork were needed.

## Inherited limitations

- The default wishlist references `images/1-28-500x500.jpg`, which is absent from
  the supplied export. The reference remains; provide the approved salt product
  image at `web/static/web/images/1-28-500x500.jpg` to resolve it. No unrelated image
  was substituted. The quick-view image also starts with an intentionally empty
  source until a product is selected.
- Standalone cart/checkout/payment pages contain hardcoded demo data and local UI
  behavior. The shared cart drawer uses local storage; this does not make the
  standalone demo checkout a complete transaction flow. Unifying these screens
  with a validated server-side order model remains backend work.
- Forms, account management, order tracking, and payment screens are demonstrations,
  not live commerce integrations. Existing copy, metadata, theme scripts, and third-
  party dependencies are preserved, including original noindex settings.
- Historical local-storage records from an older deployment can contain legacy
  image URLs. Clear demo browser storage when testing a fresh migration.
- Redis, CDN, and browser cache policies have not been configured. Static assets
  are collected, but a production web server must serve that directory.
