import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.templatetags.static import static


def banner_upload(instance, filename):
    # Separate CMS banners by year/month; unique names avoid stale browser caches.
    return f'cms/banners/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}'


def validate_destination(value):
    # Storefront-relative links only: no javascript:, external redirects or //host.
    if not value.startswith('/') or value.startswith('//') or '\\' in value or any(ord(c) < 32 for c in value):
        raise ValidationError('Use a site path beginning with /, for example /shop/.')


class Banner(models.Model):
    title = models.CharField(max_length=120)
    badge = models.CharField(max_length=40, blank=True)
    description = models.CharField(max_length=240, blank=True)
    image = models.ImageField(upload_to=banner_upload, blank=True, help_text='Recommended 1170 x 548 pixels. JPG, PNG or WebP, up to 5 MB. Keep the left side clear for text.')
    fallback_image = models.CharField(max_length=40, blank=True, editable=False)
    image_alt = models.CharField(max_length=160, blank=True)
    button_label = models.CharField(max_length=30, default='Shop Now')
    destination = models.CharField(max_length=300, default='/shop/', validators=[validate_destination], help_text='A page on this site, such as /shop/. Product linking and prices will be added later.')
    position = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('position', 'pk')

    def __str__(self):
        return self.title

    def clean(self):
        if not self.image and not self.fallback_image:
            raise ValidationError({'image': 'Upload a banner image.'})

    @property
    def image_url(self):
        return self.image.url if self.image else static(f'web/images/{self.fallback_image}')


class InformationBlock(models.Model):
    slot = models.PositiveSmallIntegerField(unique=True, validators=[MinValueValidator(1), MaxValueValidator(4)])
    title = models.CharField(max_length=60)
    description = models.CharField(max_length=220)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('slot',)
        constraints = [models.CheckConstraint(condition=models.Q(slot__gte=1, slot__lte=4), name='cms_information_four_slots')]

    def __str__(self):
        return self.title
