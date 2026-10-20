from django.urls import path
from django.views.generic import RedirectView

from web import views
from web.selectors import list_pages

app_name = "web"
urlpatterns = [
    path("", views.page_view, {"page_key": "home"}, name="home-root"),
    path("api/pages/", views.page_directory, name="page-directory"),
]
urlpatterns += [
    path(page.path, views.page_view, {"page_key": page.key}, name=page.key)
    for page in list_pages()
]
urlpatterns += [
    path(page.legacy_path, RedirectView.as_view(
        pattern_name=f"web:{page.key}", permanent=True, query_string=True,
    )) for page in {page.legacy_path:page for page in list_pages()}.values()
]
