from django.test import TestCase
from catalog.models import Product, Category


class SEOTests(TestCase):
    def test_robots_txt(self):
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain; charset=utf-8')
        content = response.content.decode()
        self.assertIn('User-agent: *', content)
        self.assertIn('Allow: /', content)
        self.assertIn('Allow: /shop/', content)
        self.assertIn('Disallow: /admin/', content)
        self.assertIn('Disallow: /cart/', content)
        self.assertIn('Sitemap: https://teraifoods.co.uk/sitemap.xml', content)

    def test_sitemap_index_and_sections(self):
        # Index
        res_idx = self.client.get('/sitemap.xml')
        self.assertEqual(res_idx.status_code, 200)
        self.assertEqual(res_idx['Content-Type'], 'application/xml; charset=utf-8')
        content_idx = res_idx.content.decode()
        self.assertIn('<sitemapindex', content_idx)
        self.assertIn('https://teraifoods.co.uk/sitemap-pages.xml', content_idx)
        self.assertIn('https://teraifoods.co.uk/sitemap-products.xml', content_idx)
        self.assertIn('https://teraifoods.co.uk/sitemap-categories.xml', content_idx)
        self.assertIn('https://teraifoods.co.uk/sitemap-blogs.xml', content_idx)

        # Pages section
        res_pages = self.client.get('/sitemap-pages.xml')
        self.assertEqual(res_pages.status_code, 200)
        content_pages = res_pages.content.decode()
        self.assertIn('<urlset', content_pages)
        self.assertIn('https://teraifoods.co.uk/</loc>', content_pages)
        self.assertIn('https://teraifoods.co.uk/shop/</loc>', content_pages)
        self.assertIn('https://teraifoods.co.uk/bulk-order/</loc>', content_pages)
        self.assertIn('https://teraifoods.co.uk/blogs/</loc>', content_pages)

        # Blogs section
        res_blogs = self.client.get('/sitemap-blogs.xml')
        self.assertEqual(res_blogs.status_code, 200)
        content_blogs = res_blogs.content.decode()
        self.assertIn('https://teraifoods.co.uk/blogs/himalayan-spices-guide/</loc>', content_blogs)

        # Products section with real product
        cat = Category.objects.create(name='Pantry', slug='pantry', is_active=True)
        Product.objects.create(name='Organic Himalayan Basmati Rice', slug='organic-basmati-rice',
                               category=cat, regular_price=15, is_published=True, is_active=True)
        res_products = self.client.get('/sitemap-products.xml')
        self.assertEqual(res_products.status_code, 200)
        content_products = res_products.content.decode()
        self.assertIn('https://teraifoods.co.uk/product-detail/?product=organic-basmati-rice</loc>', content_products)
