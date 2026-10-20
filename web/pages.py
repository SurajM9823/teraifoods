"""Explicit allowlist of approved storefront pages."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Page:
    key: str
    path: str
    template: str

    @property
    def legacy_path(self):
        return self.template.removeprefix("web/")


PAGES = {
    'about': Page('about', 'about/', 'web/about.html'),
    'blogs': Page('blogs', 'blogs/', 'web/blogs.html'),
    'bulk-order': Page('bulk-order', 'bulk-order/', 'web/bulk-order.html'),
    'cart': Page('cart', 'cart/', 'web/cart.html'),
    'checkout': Page('checkout', 'checkout/', 'web/checkout.html'),
    'contact': Page('contact', 'contact/', 'web/contact.html'),
    'home': Page('home', '', 'web/index.html'),
    'manage-profile': Page('manage-profile', 'manage-profile/', 'web/manage-profile.html'),
    'payment': Page('payment', 'payment/', 'web/payment.html'),
    'product-detail': Page('product-detail', 'product-detail/', 'web/product-detail.html'),
    'product': Page('product', 'product/', 'web/product.html'),
    'search': Page('search', 'search/', 'web/shop.html'),
    'shop': Page('shop', 'shop/', 'web/shop.html'),
    'track-order': Page('track-order', 'track-order/', 'web/track-order.html'),
    'blogs-high-protein-lentils-dhal-recipes': Page('blogs-high-protein-lentils-dhal-recipes', 'blogs/high-protein-lentils-dhal-recipes/', 'web/blogs/high-protein-lentils-dhal-recipes.html'),
    'blogs-himalayan-spices-guide': Page('blogs-himalayan-spices-guide', 'blogs/himalayan-spices-guide/', 'web/blogs/himalayan-spices-guide.html'),
    'blogs-organic-vegetables-delivery-uk': Page('blogs-organic-vegetables-delivery-uk', 'blogs/organic-vegetables-delivery-uk/', 'web/blogs/organic-vegetables-delivery-uk.html'),
    'blogs-organic-vs-conventional-food-benefits': Page('blogs-organic-vs-conventional-food-benefits', 'blogs/organic-vs-conventional-food-benefits/', 'web/blogs/organic-vs-conventional-food-benefits.html'),
    'blogs-seasonal-fruits-vegetables-calendar-uk': Page('blogs-seasonal-fruits-vegetables-calendar-uk', 'blogs/seasonal-fruits-vegetables-calendar-uk/', 'web/blogs/seasonal-fruits-vegetables-calendar-uk.html'),
    'blogs-wholesale-bulk-grocery-guide-uk': Page('blogs-wholesale-bulk-grocery-guide-uk', 'blogs/wholesale-bulk-grocery-guide-uk/', 'web/blogs/wholesale-bulk-grocery-guide-uk.html'),
}
