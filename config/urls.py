from django.contrib import admin
from django.urls import include, path
from web.backoffice.views import AdminLoginView
from web.views import health
from customers.views import profile

urlpatterns = [
    path("health/", health, name="health"),
    path("admin/system/login/", AdminLoginView.as_view()),
    path("admin/system/", admin.site.urls),
    path("admin/", include("web.backoffice.urls")),
    path("accounts/", include("allauth.urls")),
    path("manage-profile/", profile, name="customer-profile"),
    path("", include("web.urls")),
]
