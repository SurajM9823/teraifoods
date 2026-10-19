import re
import zipfile
from html.parser import HTMLParser
from urllib.parse import urlsplit
import posixpath
import hashlib
import json

from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase, TestCase
from django.urls import reverse, resolve

from web.selectors import list_pages


class AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "img", "source") and attrs.get("src"):
            self.assets.append(attrs["src"])
        if tag == "link" and attrs.get("rel") in ("stylesheet", "icon"):
            self.assets.append(attrs.get("href", ""))


class PageTests(TestCase):
    def test_all_pages_render_and_local_assets_exist(self):
        missing = set()
        for page in list_pages():
            with self.subTest(page=page.path):
                response = self.client.get(reverse(f"web:{page.key}"))
                if page.key == "manage-profile":
                    self.assertEqual(response.status_code, 302)
                    self.assertTrue(response.url.startswith('/accounts/login/'))
                    continue
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                self.assertIn("<!doctype html", html.lower())
                self.assertNotIn("{%", html)
                parser = AssetParser()
                parser.feed(html)
                for asset in parser.assets:
                    path = urlsplit(asset).path
                    if path.startswith(settings.STATIC_URL):
                        if not finders.find(path.removeprefix(settings.STATIC_URL)):
                            missing.add((page.path, path))
        self.assertFalse(missing, sorted(missing))

    def test_root_and_index_are_identical(self):
        self.assertRedirects(self.client.get("/index.html"), "/", status_code=301)

    def test_legacy_urls_redirect_and_preserve_queries(self):
        for page in list_pages():
            with self.subTest(page=page.key):
                response = self.client.get('/' + page.legacy_path + '?q=rice&page=2')
                self.assertRedirects(response, '/' + page.path + '?q=rice&page=2', status_code=301,
                                     fetch_redirect_response=page.key != 'manage-profile')

    def test_canonical_urls_do_not_use_html(self):
        for page in list_pages():
            self.assertNotIn('.html', reverse(f'web:{page.key}'))

    def test_css_local_dependencies_exist(self):
        root = settings.BASE_DIR / "web/static/web"
        missing = set()
        for stylesheet in (root / "css").glob("*.css"):
            for match in re.finditer(r"url\(\s*['\"]?([^)'\"\s]+)", stylesheet.read_text(encoding="utf-8")):
                url = urlsplit(match[1])
                if url.scheme or url.netloc or not url.path:
                    continue
                if not (stylesheet.parent / url.path).is_file():
                    missing.add((stylesheet.name, url.path))
        self.assertFalse(missing, sorted(missing))

    def test_internal_page_links_are_clean_and_resolve(self):
        routes = {"/" + page.path for page in list_pages()}
        for page in list_pages():
            html = self.client.get('/' + page.path).content.decode()
            for match in re.finditer(r'href="([^"]+)"', html):
                url = urlsplit(match[1])
                if url.scheme or url.netloc or not url.path or url.path.startswith(('/static/', '/cdn-cgi/')):
                    continue
                self.assertNotIn('.html', url.path, (page.path, match[1]))
                resolved = posixpath.normpath(posixpath.join('/' + posixpath.dirname(page.path), url.path))
                if resolved.startswith('/accounts/'):
                    self.assertIsNotNone(resolve(resolved))
                else:
                    self.assertIn(resolved.rstrip('/'), {route.rstrip('/') for route in routes}, (page.path, match[1]))

    def test_underscore_templates_survive(self):
        self.assertContains(self.client.get("/"), "{{{ data.variation.price_html }}}")

    def test_public_directory_uses_named_routes(self):
        response = self.client.get(reverse("web:page-directory"))
        self.assertEqual(response.status_code, 200)
        for page in response.json()["pages"]:
            self.assertEqual(self.client.get(page["url"]).status_code,
                             302 if page['url'] == '/manage-profile/' else 200)
        self.assertEqual(len(response.json()["pages"]), len(list_pages()))

    def test_unknown_pages_are_not_arbitrary_templates(self):
        for path in ("/missing.html", "/blogs/missing.html", "/config/settings/base.py"):
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_page_endpoints_are_read_only(self):
        self.assertEqual(self.client.post("/checkout/").status_code, 405)
        self.assertEqual(self.client.post("/api/pages/").status_code, 405)
        self.assertEqual(self.client.head("/").status_code, 200)

    def test_approved_styles_and_media_are_unchanged(self):
        with zipfile.ZipFile(settings.BASE_DIR / "docs/original-frontend.zip") as archive:
            for name in archive.namelist():
                if name.startswith(("css/", "images/", "fonts/")) and name != "css/terai-interactive.css":
                    with self.subTest(asset=name):
                        self.assertEqual(archive.read(name), (settings.BASE_DIR / "web/static/web" / name).read_bytes())

    def test_inline_styles_are_unchanged_except_asset_urls(self):
        # Current approved styles include the owner's later Shop edits and About redirect.
        baseline = json.loads((settings.BASE_DIR / 'web/tests/fixtures/inline_styles.json').read_text())
        for page in list_pages():
            if page.key == 'manage-profile':
                continue  # Replaced demo profile with a protected account page.
            html = self.client.get('/' + page.path).content.decode()
            styles = re.findall(r'<style\b[^>]*>([\s\S]*?)</style>', html)
            normalized = [re.sub(r'(?:/static/web/|(?:\.\./)+|\./)(?=(?:images|fonts|css|js)/)', '', style).replace('\r\n', '\n') for style in styles]
            self.assertEqual([hashlib.sha256(style.encode()).hexdigest() for style in normalized], baseline[page.key], page.path)
