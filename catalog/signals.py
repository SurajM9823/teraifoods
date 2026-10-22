from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Category, Subcategory
from django.core.cache import cache
from .content import invalidate_categories, CACHE_ERRORS
from .models import Product, ProductImage, CatalogRevision, PackageItem
from django.db.models import F


@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
@receiver(post_save, sender=Subcategory)
@receiver(post_delete, sender=Subcategory)
def categories_changed(sender, **kwargs):
    transaction.on_commit(invalidate_categories)


@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
@receiver(post_save, sender=ProductImage)
@receiver(post_delete, sender=ProductImage)
@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
@receiver(post_save, sender=Subcategory)
@receiver(post_delete, sender=Subcategory)
def product_cache_changed(sender, instance=None, **kwargs):
    revision, _ = CatalogRevision.objects.get_or_create(pk=1)
    CatalogRevision.objects.filter(pk=revision.pk).update(version=F('version') + 1)
    
    product_id = None
    if sender == Product and instance:
        product_id = instance.pk
    elif sender == ProductImage and instance:
        product_id = instance.product_id

    try:
        cache.delete('catalog:revision:version')
        if product_id:
            recent = cache.get('catalog:revision:changed_ids')
            if not isinstance(recent, list):
                recent = []
            if product_id not in recent:
                recent.append(product_id)
            for package_id in PackageItem.objects.filter(product_id=product_id).values_list('package__product_id',flat=True):
                if package_id not in recent:
                    recent.append(package_id)
            cache.set('catalog:revision:changed_ids', recent[-50:], 300)
    except CACHE_ERRORS:
        pass
    def update_redis_revision():
        try:
            rev = CatalogRevision.objects.filter(pk=revision.pk).values_list('version', flat=True).first()
            if rev:
                cache.set('catalog:revision:version', rev, 86400)
        except CACHE_ERRORS:
            pass
    transaction.on_commit(update_redis_revision)
