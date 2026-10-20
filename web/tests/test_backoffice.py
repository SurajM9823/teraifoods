from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


class BackofficeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            username="store-admin", password="Test-only-password-746!", is_staff=True,
        )
        cls.customer = get_user_model().objects.create_user(
            username="customer", password="Test-only-password-746!",
        )
        cls.inactive = get_user_model().objects.create_user(
            username="inactive-admin", password="Test-only-password-746!",
            is_staff=True, is_active=False,
        )

    def test_login_routes_and_dashboard_protection(self):
        for url in ("/admin/login", "/admin/login/", "/admin/system/login/"):
            self.assertContains(self.client.get(url), "Welcome back.")
        for url in ("/admin/", "/admin/dashboard", "/admin/dashboard/"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith("/admin/login?next="))

    def test_staff_can_login_and_view_real_counts(self):
        response = self.client.post(reverse("backoffice:login"), {
            "username": "store-admin", "password": "Test-only-password-746!",
        })
        self.assertRedirects(response, reverse("backoffice:dashboard"))
        dashboard = self.client.get(reverse("backoffice:dashboard"))
        self.assertEqual(dashboard.context["user_counts"], {"total": 3, "active": 2, "staff": 1})
        self.assertContains(dashboard, "Welcome back, store-admin.")
        self.assertIn("no-store", dashboard.headers["Cache-Control"])

    def test_non_staff_and_inactive_users_cannot_login(self):
        for username in ("customer", "inactive-admin"):
            with self.subTest(username=username):
                response = self.client.post(reverse("backoffice:login"), {
                    "username": username, "password": "Test-only-password-746!",
                })
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertNotIn("_auth_user_id", self.client.session)

    def test_authenticated_customer_cannot_view_dashboard(self):
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse("backoffice:dashboard")).status_code, 302)

    def test_login_rejects_external_next_url(self):
        response = self.client.post(reverse("backoffice:login"), {
            "username": "store-admin", "password": "Test-only-password-746!",
            "next": "https://untrusted.example/",
        })
        self.assertRedirects(response, reverse("backoffice:dashboard"))

    def test_login_keeps_safe_next_url(self):
        response = self.client.post(reverse("backoffice:login"), {
            "username": "store-admin", "password": "Test-only-password-746!",
            "next": "/admin/dashboard",
        })
        self.assertRedirects(response, "/admin/dashboard")

    def test_login_and_logout_enforce_csrf(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("backoffice:login"), {
            "username": "store-admin", "password": "Test-only-password-746!",
        })
        self.assertEqual(response.status_code, 403)
        client.force_login(self.staff)
        self.assertEqual(client.post(reverse("backoffice:logout")).status_code, 403)

    def test_logout_is_post_only_and_ends_session(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("backoffice:logout")).status_code, 405)
        response = self.client.post(reverse("backoffice:logout"))
        self.assertRedirects(response, reverse("backoffice:login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_original_django_admin_stays_available(self):
        self.client.force_login(self.staff)
        self.assertEqual(reverse("admin:index"), "/admin/system/")
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_dashboard_uses_bounded_queries(self):
        from web.backoffice.selectors import get_dashboard_summary

        with self.assertNumQueries(2):
            summary = get_dashboard_summary(user=self.staff)
            list(summary["recent_activity"])

    def test_all_workspace_pages_require_login(self):
        routes = [
            "/admin/",
            "/admin/orders/",
            "/admin/bulk-orders/",
            "/admin/pos/",
            "/admin/products/",
            "/admin/analytics/",
            "/admin/customers/",
            "/admin/site-settings/",
            "/admin/pricing-tier-groups/",
        ]
        for url in routes:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith("/admin/login?next="))

    def test_staff_can_access_all_workspace_pages_and_see_ordered_sidebar(self):
        self.client.force_login(self.staff)
        expected_sidebar_items = [
            "Overview",
            "Orders",
            "Bulk Inquiries",
            "POS",
            "Products",
            "Web Analytics",
            "Customers",
            "Site Settings",
            "Pricing &amp; Tier Group",
        ]
        pages = [
            ("backoffice:dashboard", "Overview"),
            ("backoffice:orders", "Orders"),
            ("backoffice:bulk-orders", "Bulk Order Inquiries"),
            ("backoffice:pos", "POS"),
            ("backoffice:products", "Products"),
            ("backoffice:analytics", "Web Analytics"),
            ("backoffice:customers", "Customers"),
            ("backoffice:site-settings", "Site Settings"),
            ("backoffice:pricing-tier-groups", "Pricing &amp; Tier Group"),
        ]

        for url_name, title in pages:
            with self.subTest(page=title):
                response = self.client.get(reverse(url_name))
                if url_name in ('backoffice:products', 'backoffice:orders'):
                    # Product and Order management now require explicit catalog permissions.
                    self.assertEqual(response.status_code, 403)
                    continue
                self.assertEqual(response.status_code, 200)
                content = response.content.decode("utf-8")

                # Verify each of the 8 items is present in the sidebar
                sidebar_start = content.find('id="admin-sidebar"')
                sidebar_end = content.find('</aside>', sidebar_start)
                sidebar_html = content[sidebar_start:sidebar_end]

                for item in expected_sidebar_items:
                    self.assertIn(item, sidebar_html)

                # Verify removed items are NOT in the sidebar
                self.assertNotIn("Content", sidebar_html)
                self.assertNotIn("Django administration", sidebar_html)

                # Verify relative order of sidebar links
                last_pos = 0
                for item in expected_sidebar_items:
                    pos = sidebar_html.find(item, last_pos)
                    self.assertNotEqual(pos, -1, f"Sidebar item '{item}' not found in expected order")
                    last_pos = pos

