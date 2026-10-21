from datetime import datetime
from django.http import HttpResponse, Http404
from django.views.decorators.http import require_GET
from django.views.decorators.cache import cache_page
from catalog.models import Product, Category

SITE_DOMAIN = "https://teraifoods.co.uk"


@require_GET
def robots_txt(request):
    content = f"""User-agent: *
Allow: /
Allow: /shop/
Allow: /product-detail/
Allow: /blogs/
Allow: /bulk-order/
Allow: /contact/
Allow: /about/
Allow: /track-order/
Disallow: /admin/
Disallow: /api/
Disallow: /cart/
Disallow: /checkout/
Disallow: /payment/
Disallow: /manage-profile/
Disallow: /accounts/

Sitemap: {SITE_DOMAIN}/sitemap.xml
"""
    return HttpResponse(content, content_type="text/plain; charset=utf-8")


@require_GET
@cache_page(3600)
def sitemap_index(request):
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap>
        <loc>{SITE_DOMAIN}/sitemap-pages.xml</loc>
    </sitemap>
    <sitemap>
        <loc>{SITE_DOMAIN}/sitemap-products.xml</loc>
    </sitemap>
    <sitemap>
        <loc>{SITE_DOMAIN}/sitemap-categories.xml</loc>
    </sitemap>
    <sitemap>
        <loc>{SITE_DOMAIN}/sitemap-blogs.xml</loc>
    </sitemap>
</sitemapindex>"""
    return HttpResponse(xml, content_type="application/xml; charset=utf-8")


@require_GET
@cache_page(3600)
def sitemap_section(request, section):
    now_str = datetime.utcnow().strftime("%Y-%m-%d")

    if section == "pages":
        pages = [
            ("", "1.0", "daily"),
            ("shop/", "0.9", "daily"),
            ("bulk-order/", "0.8", "weekly"),
            ("blogs/", "0.8", "daily"),
            ("contact/", "0.7", "monthly"),
            ("about/", "0.6", "monthly"),
            ("track-order/", "0.6", "weekly"),
        ]
        urls_xml = []
        for path, priority, freq in pages:
            urls_xml.append(f"""    <url>
        <loc>{SITE_DOMAIN}/{path}</loc>
        <lastmod>{now_str}</lastmod>
        <changefreq>{freq}</changefreq>
        <priority>{priority}</priority>
    </url>""")
        body = "\n".join(urls_xml)

    elif section == "products":
        urls_xml = []
        try:
            products = Product.objects.filter(is_active=True, is_published=True, is_archived=False)
            for p in products:
                lastmod = p.updated_at.strftime("%Y-%m-%d") if hasattr(p, 'updated_at') and p.updated_at else now_str
                image_tag = ""
                if p.image_url:
                    img_url = p.image_url if p.image_url.startswith("http") else f"{SITE_DOMAIN}{p.image_url}"
                    clean_name = p.name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                    image_tag = f"""
        <image:image>
            <image:loc>{img_url}</image:loc>
            <image:title>{clean_name}</image:title>
        </image:image>"""
                urls_xml.append(f"""    <url>
        <loc>{SITE_DOMAIN}/product-detail/?product={p.slug}</loc>
        <lastmod>{lastmod}</lastmod>
        <changefreq>weekly</changefreq>
        <priority>0.8</priority>{image_tag}
    </url>""")
        except Exception:
            pass
        body = "\n".join(urls_xml)

    elif section == "categories":
        urls_xml = []
        try:
            categories = Category.objects.filter(is_active=True)
            for c in categories:
                urls_xml.append(f"""    <url>
        <loc>{SITE_DOMAIN}/shop/?category={c.slug}</loc>
        <lastmod>{now_str}</lastmod>
        <changefreq>weekly</changefreq>
        <priority>0.7</priority>
    </url>""")
        except Exception:
            pass
        body = "\n".join(urls_xml)

    elif section == "blogs":
        blogs = [
            "blogs/high-protein-lentils-dhal-recipes/",
            "blogs/himalayan-spices-guide/",
            "blogs/organic-vegetables-delivery-uk/",
            "blogs/organic-vs-conventional-food-benefits/",
            "blogs/seasonal-fruits-vegetables-calendar-uk/",
            "blogs/wholesale-bulk-grocery-guide-uk/",
        ]
        urls_xml = []
        for b in blogs:
            urls_xml.append(f"""    <url>
        <loc>{SITE_DOMAIN}/{b}</loc>
        <lastmod>{now_str}</lastmod>
        <changefreq>monthly</changefreq>
        <priority>0.7</priority>
    </url>""")
        body = "\n".join(urls_xml)

    else:
        raise Http404("Sitemap section not found")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
{body}
</urlset>"""
    return HttpResponse(xml, content_type="application/xml; charset=utf-8")

