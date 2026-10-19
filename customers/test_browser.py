import os
import secrets
import shutil
import subprocess
from unittest import skipUnless
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.cache import cache


@skipUnless(os.environ.get('RUN_CUSTOMER_NAVIGATION_TESTS') == '1', 'Optional Edge browser test')
class CustomerNavigationTests(StaticLiveServerTestCase):
    def test_login_home_and_profile_navigation(self):
        cache.clear()
        password = secrets.token_urlsafe(24)
        user = get_user_model().objects.create_user('customer-browser', 'customer@example.test', password)
        EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
        result = subprocess.run(
            [shutil.which('node') or 'node', str(settings.BASE_DIR / 'tools/customer_navigation_smoke.cjs')],
            cwd=settings.BASE_DIR,
            env={**os.environ, 'CUSTOMER_TEST_URL': self.live_server_url,
                 'CUSTOMER_TEST_PASSWORD': password},
            capture_output=True, text=True, timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
