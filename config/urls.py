from django.contrib import admin
from django.urls import include, path
from web.backoffice.views import AdminLoginView
from web.views import health
from web import seo_views
from customers.views import profile
from catalog import api as product_api
from catalog import admin_api
from orders import backoffice as order_admin
from orders import bulk
from catalog import package_admin
from cms.contact import submit as contact_submit

urlpatterns = [
    path("api/contact/inquiries/", contact_submit),
    path('admin/packages/',package_admin.manage,name='package-new'),
    path('admin/packages/<int:pk>/',package_admin.manage,name='package-edit'),
    path('api/bulk/requests/',bulk.requests),
    path('api/bulk/access/',bulk.access),
    path('api/bulk/requests/<uuid:public_id>/',bulk.detail),
    path('admin/bulk-orders',bulk.admin_index),
    path('admin/bulk-orders/',bulk.admin_index),
    path('admin/bulk-inquiries',bulk.admin_index),
    path('admin/bulk-inquiries/',bulk.admin_index),
    path('admin/bulk-orders/<uuid:public_id>/',bulk.admin_detail,name='bulk-admin-detail'),
    path("admin/orders", order_admin.index),
    path("admin/orders/", order_admin.index),
    path("admin/orders/reviews/", order_admin.reviews, name="order-admin-reviews"),
    path("admin/orders/<uuid:public_id>/", order_admin.detail, name="order-admin-detail"),
    path("api/orders/", include("orders.urls")),
    path("admin/delivery/", include("delivery.urls")),
    path("api/admin/products/", admin_api.products),
    path("api/admin/products/<int:pk>/", admin_api.products),
    path("api/admin/products/<int:pk>/stock/", admin_api.stock),
    path("api/admin/products/<int:pk>/images/", admin_api.images),
    path("api/admin/<str:kind>/", admin_api.categories),
    path("api/admin/<str:kind>/<int:pk>/", admin_api.categories),
    path("api/products/", product_api.listing, name="product-list"),
    path("api/homepage/", product_api.homepage, name="product-homepage-api"),
    path("api/products/<slug:slug>/", product_api.detail, name="product-detail-api"),
    path("api/categories/", product_api.categories, name="product-categories-api"),
    path("api/checkout/reserve/", product_api.checkout, name="product-checkout"),
    path("api/cart/quote/", product_api.cart_quote, name="product-cart-quote"),
    path("api/catalog/revision/", product_api.catalog_revision, name="catalog-revision-api"),
    path("admin/products/", include("catalog.product_urls")),
    path("health/", health, name="health"),
    path("admin/system/login/", AdminLoginView.as_view()),
    path("admin/system/", admin.site.urls),
    path("admin/categories/", include("catalog.urls")),
    path("admin/cms/", include("cms.urls")),
    path("admin/", include("web.backoffice.urls")),
    path("accounts/", include("allauth.urls")),
    path("manage-profile/", profile, name="customer-profile"),
    path("robots.txt", seo_views.robots_txt, name="robots-txt"),
    path("sitemap.xml", seo_views.sitemap_index, name="sitemap-index"),
    path("sitemap-<str:section>.xml", seo_views.sitemap_section, name="sitemap-section"),
    path("", include("web.urls")),
]

from django.conf import settings
from django.conf.urls.static import static
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
