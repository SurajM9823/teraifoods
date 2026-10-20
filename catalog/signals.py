from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Category, Subcategory
from .content import invalidate_categories
from .models import Product, ProductImage, CatalogRevision
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
def product_cache_changed(sender, **kwargs):
    revision, _ = CatalogRevision.objects.get_or_create(pk=1)
    CatalogRevision.objects.filter(pk=revision.pk).update(version=F('version') + 1)
