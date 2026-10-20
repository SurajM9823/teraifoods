from django.contrib import admin
from django.urls import include, path
from web.backoffice.views import AdminLoginView
from web.views import health
from customers.views import profile
from catalog import api as product_api
from catalog import admin_api

urlpatterns = [
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
    path("", include("web.urls")),
]

from django.conf import settings
from django.conf.urls.static import static
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
