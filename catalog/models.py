from django.db import models
from django.db.models.functions import Lower
from .icons import ICON_CHOICES
from django.conf import settings
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.core.validators import MinValueValidator
import uuid


class CategoryFields(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, allow_unicode=True, help_text='Stable identifier. Generated from the name when left blank.')
    description = models.TextField(max_length=500, blank=True)
    icon = models.CharField(max_length=64, blank=True, choices=ICON_CHOICES)
    is_active = models.BooleanField(default=True)
    position = models.PositiveSmallIntegerField(default=0, help_text='Smaller numbers appear first.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ('position', 'name', 'pk')

    def __str__(self):
        return self.name


class Category(CategoryFields):
    legacy_key = models.CharField(max_length=40, blank=True, editable=False)
    menu_image = models.CharField(max_length=40, blank=True, choices=[
        (name + '.svg', label) for name, label in (
            ('apple', 'Fruit'), ('meat', 'Meat'), ('boiled-egg', 'Breakfast'),
            ('toast-bread', 'Bread'), ('cup', 'Drinks'), ('snowflake', 'Frozen'),
            ('bar', 'Snacks'), ('wheat', 'Grocery'), ('scoop', 'Household'),
            ('toilet-paper', 'Healthcare'), ('baby-boy', 'Baby'),
        )
    ], help_text='Original storefront artwork. A selected Font Awesome icon takes priority.')
    class Meta(CategoryFields.Meta):
        abstract = False
        verbose_name_plural = 'categories'
        constraints = [
            models.UniqueConstraint(Lower('name'), name='catalog_category_name_ci'),
            models.UniqueConstraint(fields=['slug'], name='catalog_category_slug_unique'),
        ]


class Subcategory(CategoryFields):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='subcategories')

    class Meta(CategoryFields.Meta):
        abstract = False
        verbose_name_plural = 'subcategories'
        constraints = [
            models.UniqueConstraint(Lower('name'), 'category', name='catalog_subcategory_name_ci'),
            models.UniqueConstraint(fields=['category', 'slug'], name='catalog_subcategory_slug_unique'),
        ]

    @property
    def effective_active(self):
        return self.is_active and self.category.is_active


class Product(models.Model):
    name = models.CharField(max_length=300)
    slug = models.SlugField(max_length=320, unique=True)
    sku = models.CharField(max_length=80, blank=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products', null=True, blank=True)
    subcategory = models.ForeignKey(Subcategory, on_delete=models.PROTECT, related_name='products', null=True, blank=True)
    regular_price = models.DecimalField(max_digits=12, decimal_places=2)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    weight = models.DecimalField(max_digits=10, decimal_places=3, default=Decimal('150'),
        validators=[MinValueValidator(Decimal('0.001'))], help_text='Shipping weight per sellable unit.')
    weight_unit = models.CharField(max_length=2, choices=[('g', 'gm (grams)'), ('kg', 'kg (kilograms)')], default='g')
    is_active = models.BooleanField(default=True)
    is_published = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    new_arrival = models.BooleanField(default=False)
    featured = models.BooleanField(default=False)
    best_seller = models.BooleanField(default=False)
    stock = models.PositiveIntegerField(default=0, editable=False)
    stock_confirmed = models.BooleanField(default=False, editable=False)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    display_order = models.PositiveIntegerField(default=100000)
    rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    review_count = models.PositiveIntegerField(default=0)
    legacy_key = models.CharField(max_length=100, null=True, blank=True, unique=True, editable=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('pk',)
        indexes = [
            models.Index(fields=['is_active', 'is_published', 'is_archived', 'id'], name='product_public_idx'),
            models.Index(fields=['category', 'id'], name='product_category_idx'),
            models.Index(fields=['subcategory', 'id'], name='product_subcategory_idx'),
            models.Index(fields=['regular_price', 'id'], name='product_price_idx'),
            models.Index(fields=['new_arrival', 'id'], name='product_new_idx'),
            models.Index(fields=['featured', 'id'], name='product_featured_idx'),
            models.Index(fields=['best_seller', 'id'], name='product_best_idx'),
            models.Index(fields=['display_order', 'id'], name='product_order_idx'),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(regular_price__gt=0), name='product_positive_price'),
            models.CheckConstraint(condition=models.Q(sale_price__isnull=True) | (models.Q(sale_price__gt=0) & models.Q(sale_price__lt=models.F('regular_price'))), name='product_valid_discount'),
            models.CheckConstraint(condition=models.Q(featured=False) | models.Q(sale_price__isnull=False), name='featured_requires_discount'),
            models.CheckConstraint(condition=models.Q(is_published=False) | models.Q(category__isnull=False), name='published_requires_category'),
            models.CheckConstraint(condition=models.Q(weight__gt=0), name='product_positive_weight'),
            models.CheckConstraint(condition=models.Q(weight_unit__in=['g', 'kg']), name='product_weight_unit_valid'),
        ]

    def clean(self):
        errors = {}
        if self.subcategory_id and self.subcategory.category_id != self.category_id:
            errors['subcategory'] = 'Select a subcategory belonging to this category.'
        if self.featured and self.sale_price is None:
            errors['sale_price'] = 'Featured products require a discounted price.'
        if self.is_published and not self.category_id:
            errors['category'] = 'Published products require a category.'
        if errors:
            raise ValidationError(errors)

    @property
    def weight_grams(self):
        return self.weight * (Decimal('1000') if self.weight_unit == 'kg' else Decimal('1'))

    @property
    def price(self):
        return self.sale_price if self.sale_price is not None else self.regular_price

    @property
    def discount_percent(self):
        return int(((self.regular_price - self.price) * 100 / self.regular_price).quantize(Decimal('1'))) if self.regular_price else 0

    @property
    def main_image(self):
        return next((image for image in self.images.all() if image.is_main), None)

    @property
    def image_url(self):
        return self.main_image.url if self.main_image else ''

    @property
    def available(self):
        return self.is_active and self.is_published and not self.is_archived and self.stock_confirmed and self.stock > 0

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='images')
    source = models.CharField(max_length=500)
    variants = models.JSONField(default=dict)
    alt = models.CharField(max_length=300, blank=True)
    is_main = models.BooleanField(default=False)
    position = models.PositiveSmallIntegerField(default=0)
    digest = models.CharField(max_length=64)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()

    class Meta:
        ordering = ('position', 'pk')
        constraints = [
            models.UniqueConstraint(fields=['product'], condition=models.Q(is_main=True), name='one_product_main_image'),
            models.CheckConstraint(condition=models.Q(position__lte=4), name='image_position_limit'),
        ]

    @property
    def url(self):
        from .media import media_url
        return media_url(self.source)

    @property
    def webp_srcset(self):
        from .media import media_url
        return ', '.join(f'{media_url(path)} {width}w' for width, path in self.variants.get('webp', {}).items())

    @property
    def avif_srcset(self):
        from .media import media_url
        return ', '.join(f'{media_url(path)} {width}w' for width, path in self.variants.get('avif', {}).items())


class ImmutableAuditQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('Stock audit records are immutable.')

    def delete(self):
        raise ValidationError('Stock audit records are immutable.')


class StockAudit(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='stock_history')
    previous_quantity = models.PositiveIntegerField()
    adjustment = models.IntegerField()
    new_quantity = models.PositiveIntegerField()
    adjustment_type = models.CharField(max_length=30, choices=[(v, v.replace('_', ' ').title()) for v in ('initial', 'manual_increase', 'manual_decrease', 'order', 'cancellation', 'return', 'correction')])
    reason = models.CharField(max_length=500)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    idempotency_key = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = ImmutableAuditQuerySet.as_manager()

    class Meta:
        ordering = ('-created_at', '-pk')
        constraints = [models.CheckConstraint(condition=models.Q(new_quantity=models.F('previous_quantity') + models.F('adjustment')), name='stock_audit_balances')]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Stock audit records are immutable.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Stock audit records are immutable.')


class Order(models.Model):
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    public_id = models.UUIDField(unique=True, null=True, editable=False)
    email = models.EmailField(blank=True)
    recipient_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.JSONField(default=dict)
    billing_address = models.JSONField(default=dict, blank=True)
    currency = models.CharField(max_length=3, default='GBP')
    payment_method = models.CharField(max_length=20, default='stripe')
    payment_status = models.CharField(max_length=20, default='pending')
    fulfilment_status = models.CharField(max_length=30, default='pending_payment', db_index=True)
    cancellation_status = models.CharField(max_length=20, default='none')
    refund_status = models.CharField(max_length=20, default='none')
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    version = models.PositiveIntegerField(default=0)
    guest_access_version = models.PositiveIntegerField(default=1)
    reservation_expires_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    tracking_reference = models.CharField(max_length=150, blank=True)
    tracking_url = models.URLField(blank=True)
    assigned_driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='delivery_assignments')
    delivery_pin_hash = models.CharField(max_length=128, blank=True)
    delivery_pin_expires_at = models.DateTimeField(null=True, blank=True)
    delivery_pin_attempts = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    idempotency_key = models.CharField(max_length=100, unique=True)
    request_digest = models.CharField(max_length=64)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_weight_grams = models.DecimalField(max_digits=16, decimal_places=3, null=True, blank=True)
    delivery_min_days = models.PositiveSmallIntegerField(null=True, blank=True)
    delivery_max_days = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, default='reserved', choices=[('reserved', 'Reserved'), ('cancelled', 'Cancelled')])
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def number(self):
        return f'TF-{self.pk:08d}'

    def save(self, *args, **kwargs):
        if self.public_id is None:
            self.public_id = uuid.uuid4()
        return super().save(*args, **kwargs)


class OrderLine(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='lines')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    unit_weight_grams = models.DecimalField(max_digits=13, decimal_places=3, null=True, blank=True)
    product_name = models.CharField(max_length=300, blank=True)
    product_image = models.CharField(max_length=1000, blank=True)
    product_sku = models.CharField(max_length=80, blank=True)


class CatalogRevision(models.Model):
    version = models.PositiveBigIntegerField(default=1)
