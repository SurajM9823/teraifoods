from django.urls import path

from . import views

app_name = "backoffice"
urlpatterns = [
    # 1. Overview
    path("", views.dashboard, name="dashboard"),
    path("dashboard", views.dashboard, name="dashboard-alias"),
    path("dashboard/", views.dashboard),

    # 2. Orders
    path("orders", views.orders, name="orders-alias"),
    path("orders/", views.orders, name="orders"),

    # Bulk Order Inquiries
    path("bulk-orders", views.bulk_orders, name="bulk-orders-alias"),
    path("bulk-orders/", views.bulk_orders, name="bulk-orders"),
    path("bulk-inquiries", views.bulk_orders),
    path("bulk-inquiries/", views.bulk_orders),

    # 3. POS
    path("pos", views.pos, name="pos-alias"),
    path("pos/", views.pos, name="pos"),

    # 4. Products
    path("products", views.products, name="products-alias"),
    path("products/", views.products, name="products"),

    # 5. Web Analytics
    path("analytics", views.web_analytics, name="analytics-alias"),
    path("analytics/", views.web_analytics, name="analytics"),
    path("web-analytics", views.web_analytics),
    path("web-analytics/", views.web_analytics),

    # 6. Customers
    path("customers", views.customers, name="customers-alias"),
    path("customers/", views.customers, name="customers"),

    # 7. Site Settings
    path("settings", views.site_settings, name="site-settings-alias"),
    path("settings/", views.site_settings),
    path("site-settings", views.site_settings),
    path("site-settings/", views.site_settings, name="site-settings"),

    # 8. Pricing & Tier Group
    path("pricing-tier-groups", views.pricing_tier_groups, name="pricing-tier-groups-alias"),
    path("pricing-tier-groups/", views.pricing_tier_groups, name="pricing-tier-groups"),
    path("pricing", views.pricing_tier_groups),
    path("pricing/", views.pricing_tier_groups),

    # Auth
    path("login", views.AdminLoginView.as_view(), name="login"),
    path("login/", views.AdminLoginView.as_view()),
    path("logout", views.AdminLogoutView.as_view(), name="logout"),
]
