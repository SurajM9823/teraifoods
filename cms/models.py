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


class ContactSettings(models.Model):
    # Direct Hotline & Hours
    phone = models.CharField(max_length=50, default='+44 20 7946 0912', help_text='Direct Office Line')
    operating_hours = models.CharField(max_length=100, default='24/7 Support', help_text='Customer service operating hours')

    # WhatsApp Fast Support
    whatsapp_number = models.CharField(max_length=50, default='+447700900077', help_text='WhatsApp helpline with country code')
    whatsapp_title = models.CharField(max_length=100, default='WhatsApp Fast Support')
    whatsapp_subtitle = models.CharField(max_length=150, default='Chat live with dispatch rep')

    # Department Emails
    support_email = models.EmailField(default='support@teraifood.co.uk')
    support_email_sla = models.CharField(max_length=50, default='< 2 HR SLA')
    support_email_subtext = models.CharField(max_length=150, default='Orders, tracking, returns & refunds')

    wholesale_email = models.EmailField(default='wholesale@teraifood.co.uk')
    wholesale_email_subtext = models.CharField(max_length=150, default='Bulk purchase orders & commercial B2B')

    # Head Office Location
    office_title = models.CharField(max_length=120, default='London HQ & Central Depot')
    office_address = models.CharField(max_length=255, default='Unit 4B Peninsula Park, London SE10 0ER, UK')

    # Social Channels
    social_heading = models.CharField(max_length=100, default='Social Channels')
    social_badge = models.CharField(max_length=50, default='CONNECT')
    social_text = models.CharField(max_length=255, default='Follow us for new harvest arrivals, seasonal promotions, and rapid customer messaging.')
    facebook_url = models.URLField(blank=True, default='https://www.facebook.com/')
    twitter_url = models.URLField(blank=True, default='https://www.twitter.com/')
    instagram_url = models.URLField(blank=True, default='https://www.instagram.com/')
    linkedin_url = models.URLField(blank=True, default='https://www.linkedin.com/')

    # UK Delivery Hubs Map
    map_badge = models.CharField(max_length=50, default='4 HUBS ACTIVE')
    map_subtitle = models.CharField(max_length=255, default='Temperature-controlled fleet operates out of all 4 key hubs to guarantee next-day delivery across mainland UK.')

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Contact Settings'
        verbose_name_plural = 'Contact Settings'

    def __str__(self):
        return f'Contact Settings (Updated {self.updated_at.strftime("%d %b %Y") if self.updated_at else "Initial"})'

    @property
    def whatsapp_clean(self):
        import re
        raw = re.sub(r'[^0-9]', '', str(self.whatsapp_number or ''))
        if raw.startswith('0') and len(raw) == 11:
            raw = '44' + raw[1:]
        return raw or '447700900077'

    @property
    def phone_clean(self):
        import re
        return re.sub(r'[^0-9+]', '', str(self.phone or ''))

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


class FAQItem(models.Model):
    question = models.CharField(max_length=255)
    answer = models.TextField()
    order = models.PositiveIntegerField(default=0, help_text='Display order (lower numbers appear first)')
    is_active = models.BooleanField(default=True, help_text='Whether this FAQ is shown on the website')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('order', 'id')
        verbose_name = 'FAQ Item'
        verbose_name_plural = 'FAQ Items'

    def __str__(self):
        return self.question


class ContactInquiry(models.Model):
    STATUS_CHOICES = (
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    )

    TOPIC_CHOICES = (
        ('order-status', 'Live Order Status & Tracking'),
        ('produce-quality', 'Produce Freshness Guarantee'),
        ('wholesale-quote', 'Wholesale & Bulk Quote'),
        ('delivery-postcode', 'Postcode Cold-Chain Query'),
        ('refund-request', 'Refund or Replacement'),
        ('other', 'General Customer Question'),
    )

    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    topic = models.CharField(max_length=80, default='other')
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    admin_notes = models.TextField(blank=True, help_text='Internal staff notes regarding this inquiry')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'Support Inquiry'
        verbose_name_plural = 'Support Inquiries'

    def __str__(self):
        return f'Inquiry #{self.id} from {self.name} ({self.get_status_display()})'

    @property
    def topic_display(self):
        topics_dict = dict(self.TOPIC_CHOICES)
        return topics_dict.get(self.topic, self.topic or 'General Question')



class ContactHub(models.Model):
    name = models.CharField(max_length=120)
    tag = models.CharField(max_length=60)
    legend = models.CharField(max_length=100)
    description = models.TextField()
    latitude = models.FloatField(validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.FloatField(validators=[MinValueValidator(-180), MaxValueValidator(180)])
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('order', 'pk')

    def __str__(self):
        return self.name
