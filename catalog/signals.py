from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Category, Subcategory
from .content import invalidate_categories


@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
@receiver(post_save, sender=Subcategory)
@receiver(post_delete, sender=Subcategory)
def categories_changed(sender, **kwargs):
    transaction.on_commit(invalidate_categories)
