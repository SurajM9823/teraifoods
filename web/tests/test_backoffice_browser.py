"""Optional real browser coverage using an isolated Django test database."""
import os
import secrets
import shutil
import subprocess
from unittest import skipUnless

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase


@skipUnless(os.environ.get("RUN_ADMIN_BROWSER_TESTS") == "1", "Optional Edge browser test")
class AdminBrowserTests(StaticLiveServerTestCase):
    def test_login_sidebar_and_logout(self):
        password = secrets.token_urlsafe(24)
        get_user_model().objects.create_user(username="browser-admin", password=password, is_staff=True)
        env = {**os.environ, "ADMIN_TEST_URL": self.live_server_url,
               "ADMIN_TEST_USER": "browser-admin", "ADMIN_TEST_PASSWORD": password}
        result = subprocess.run(
            [shutil.which("node") or "node", str(settings.BASE_DIR / "tools/admin_browser_smoke.cjs")],
            cwd=settings.BASE_DIR, env=env, capture_output=True, text=True, timeout=100,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)


@skipUnless(os.environ.get("RUN_STOREFRONT_BROWSER_TESTS") == "1", "Optional storefront Edge test")
class StorefrontBrowserTests(StaticLiveServerTestCase):
    def test_clean_routes_and_cart(self):
        env = {**os.environ, "STOREFRONT_TEST_URL": self.live_server_url}
        result = subprocess.run(
            [shutil.which("node") or "node", str(settings.BASE_DIR / "tools/browser_smoke.cjs")],
            cwd=settings.BASE_DIR, env=env, capture_output=True, text=True, timeout=180,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
