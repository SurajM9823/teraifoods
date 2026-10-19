import os
import secrets
import shutil
import subprocess
from unittest import skipUnless
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.cache import cache


@skipUnless(os.environ.get('RUN_CATEGORY_BROWSER_TESTS') == '1', 'Optional Edge browser test')
class CategoryBrowserTests(StaticLiveServerTestCase):
    def test_category_management(self):
        cache.clear()
        password = secrets.token_urlsafe(24)
        get_user_model().objects.create_superuser('category-browser', 'category@example.test', password)
        result = subprocess.run(
            [shutil.which('node') or 'node', str(settings.BASE_DIR / 'tools/categories_browser_smoke.cjs')],
            cwd=settings.BASE_DIR,
            env={**os.environ, 'ADMIN_TEST_URL': self.live_server_url,
                 'ADMIN_TEST_USER': 'category-browser', 'ADMIN_TEST_PASSWORD': password},
            capture_output=True, text=True, timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
