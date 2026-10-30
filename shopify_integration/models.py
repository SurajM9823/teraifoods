"""Additive integration tables. No signals, stock operations or payment hooks."""
from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from decimal import Decimal
from catalog.models import Product


class ShopifyCatalogueProduct(Product):
    class Meta:
        proxy = True
        verbose_name = 'Shopify catalogue product'
        permissions = [('sync_shopify_draft', 'Can synchronize Shopify drafts')]


class ShopifyConnection(models.Model):
    shop_domain = models.CharField(max_length=253, unique=True, validators=[RegexValidator(
        r'\A[a-z0-9][a-z0-9-]*\.myshopify\.com\Z', 'Use the canonical myshopify.com hostname.')])
    enabled = models.BooleanField(default=False)
    api_version = models.CharField(max_length=7, default='2026-10', validators=[RegexValidator(r'\A\d{4}-(01|04|07|10)\Z')])
    publication_ids = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.shop_domain


class ChannelVariantDefinition(models.Model):
    product = models.ForeignKey('catalog.Product', on_delete=models.PROTECT, related_name='channel_variants')
    key = models.CharField(max_length=100)
    source_variant_id = models.CharField(max_length=100, blank=True)
    # Ordered [{"name": "Flavour", "value": "Cola"}]; never rewrite source metadata.
    option_values = models.JSONField(default=list)
    price_policy = models.CharField(max_length=10, choices=[('inherit', 'Inherit product'), ('explicit', 'Reviewed price')], default='inherit')
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    compare_at_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    sku = models.CharField(max_length=80, blank=True)
    weight_grams = models.DecimalField(max_digits=13, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(Decimal('0.001'))])
    image = models.ForeignKey('catalog.ProductImage', null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ('key',)
        constraints = [models.UniqueConstraint(fields=['product', 'key'], name='shopify_local_variant_key')]


class VariantReview(models.Model):
    product = models.OneToOneField('catalog.Product', on_delete=models.PROTECT)
    fingerprint = models.CharField(max_length=64)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    reviewed_at = models.DateTimeField(auto_now=True)


class ShopifyProductMapping(models.Model):
    connection = models.ForeignKey(ShopifyConnection, on_delete=models.PROTECT)
    product = models.ForeignKey('catalog.Product', on_delete=models.PROTECT)
    remote_product_gid = models.CharField(max_length=255, null=True, blank=True)
    applied_payload = models.JSONField(default=dict, blank=True)
    payload_hash = models.CharField(max_length=64, blank=True)
    desired_revision = models.PositiveBigIntegerField(default=0)
    applied_revision = models.PositiveBigIntegerField(default=0)
    status = models.CharField(max_length=20, default='not_synced')
    error_code = models.CharField(max_length=60, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['connection', 'product'], name='shopify_product_local_unique'),
            models.UniqueConstraint(fields=['connection', 'remote_product_gid'], name='shopify_product_remote_unique'),
        ]


class ShopifyVariantMapping(models.Model):
    product_mapping = models.ForeignKey(ShopifyProductMapping, on_delete=models.PROTECT)
    definition = models.ForeignKey(ChannelVariantDefinition, null=True, blank=True, on_delete=models.PROTECT)
    local_key = models.CharField(max_length=100, default='default')
    remote_variant_gid = models.CharField(max_length=255, unique=True)
    inventory_item_gid = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['product_mapping', 'local_key'], name='shopify_variant_local_unique')]


class ShopifyMediaMapping(models.Model):
    product_mapping = models.ForeignKey(ShopifyProductMapping, on_delete=models.PROTECT)
    image = models.ForeignKey('catalog.ProductImage', null=True, blank=True, on_delete=models.SET_NULL)
    digest = models.CharField(max_length=64)
    remote_file_gid = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, default='pending')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['product_mapping', 'image'], name='shopify_media_local_unique')]


class ShopifySyncJob(models.Model):
    mapping = models.ForeignKey(ShopifyProductMapping, on_delete=models.PROTECT)
    operation = models.CharField(max_length=20, choices=[('draft_sync', 'Sync draft'), ('publish', 'Explicit publish'), ('unpublish', 'Explicit unpublish')])
    idempotency_key = models.CharField(max_length=100, unique=True)
    desired_revision = models.PositiveBigIntegerField(default=0)
    status = models.CharField(max_length=20, default='pending')
    attempts = models.PositiveIntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ShopifyWebhookReceipt(models.Model):
    connection = models.ForeignKey(ShopifyConnection, on_delete=models.PROTECT)
    delivery_id = models.CharField(max_length=255)
    event_id = models.CharField(max_length=255, blank=True)
    topic = models.CharField(max_length=100)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default='pending')
    attempts = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=60, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['connection', 'delivery_id'], name='shopify_delivery_unique')]


class ShopifyOrderMapping(models.Model):
    connection = models.ForeignKey(ShopifyConnection, on_delete=models.PROTECT)
    sales_channel = models.CharField(max_length=20, default='shopify', editable=False)
    remote_order_gid = models.CharField(max_length=255)
    remote_order_name = models.CharField(max_length=100, blank=True)
    # Staging remains separate from operational orders until import isolation is implemented.
    order = models.OneToOneField('catalog.Order', null=True, blank=True, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, default='staged')
    financial_snapshot = models.JSONField(default=dict)
    remote_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['connection', 'remote_order_gid'], name='shopify_order_remote_unique'),
            models.CheckConstraint(condition=models.Q(sales_channel='shopify'), name='shopify_order_channel'),
        ]


class ShopifyOrderLineMapping(models.Model):
    order_mapping = models.ForeignKey(ShopifyOrderMapping, on_delete=models.PROTECT)
    remote_line_gid = models.CharField(max_length=255)
    line = models.OneToOneField('catalog.OrderLine', null=True, blank=True, on_delete=models.PROTECT)
    variant_mapping = models.ForeignKey(ShopifyVariantMapping, null=True, blank=True, on_delete=models.PROTECT)
    snapshot = models.JSONField(default=dict)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['order_mapping', 'remote_line_gid'], name='shopify_order_line_unique')]


class IntegrationLog(models.Model):
    connection = models.ForeignKey(ShopifyConnection, null=True, blank=True, on_delete=models.PROTECT)
    product = models.ForeignKey('catalog.Product', null=True, blank=True, on_delete=models.PROTECT)
    operation = models.CharField(max_length=30)
    status = models.CharField(max_length=20)
    # Only application-owned codes; never raw API responses, credentials or customer data.
    codes = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
