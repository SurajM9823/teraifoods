from django.utils.functional import SimpleLazyObject
from .content import category_tree, collection_links


def storefront_categories(request):
    # Resolve only when a storefront template actually renders a category block.
    return {'storefront_categories': SimpleLazyObject(category_tree),
            'storefront_collections': SimpleLazyObject(collection_links)}
