from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_safe
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db import connection, DatabaseError

from web.selectors import get_page
from web.services import build_page_directory


@require_safe
@ensure_csrf_cookie
def page_view(request, page_key):
    page = get_page(page_key)
    if page is None:
        raise Http404("Page not found")
    context = {}
    from catalog.storefront import context as product_context
    context.update(product_context(request, page.key))
    if page.key == "home":
        from cms.content import homepage_content
        context["cms_home"] = homepage_content()
    return render(request, page.template, context)


@require_safe
def page_directory(request):
    return JsonResponse(build_page_directory())


@never_cache
@require_safe
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
