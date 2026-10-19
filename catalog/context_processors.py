from django.utils.functional import SimpleLazyObject
from .content import category_tree


def storefront_categories(request):
    # Resolve only when a storefront template actually renders a category block.
    return {'storefront_categories': SimpleLazyObject(category_tree)}
