from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .content import invalidate_home
from .models import Banner, InformationBlock


@receiver(post_save, sender=Banner)
@receiver(post_delete, sender=Banner)
@receiver(post_save, sender=InformationBlock)
@receiver(post_delete, sender=InformationBlock)
def content_changed(sender, **kwargs):
    transaction.on_commit(invalidate_home)
