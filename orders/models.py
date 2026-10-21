from django.conf import settings
from django.db import models
from catalog.models import Order, OrderLine, Product


class Address(models.Model):
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='delivery_addresses')
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30)
    line1 = models.CharField(max_length=200)
    line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    county = models.CharField(max_length=100, blank=True)
    postcode = models.CharField(max_length=10)
    country = models.CharField(max_length=2, default='GB')
    instructions = models.CharField(max_length=500, blank=True)
    verification = models.CharField(max_length=30, default='manual')
    is_default = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['customer'], condition=models.Q(is_default=True), name='one_default_delivery_address')]


class CheckoutAttempt(models.Model):
    key = models.CharField(max_length=64, unique=True)
    digest = models.CharField(max_length=64)
    order = models.OneToOneField(Order, on_delete=models.PROTECT, null=True)


class Payment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name='payment')
    session_id = models.CharField(max_length=255, blank=True, db_index=True)
    session_url = models.URLField(max_length=2000, blank=True)
    intent_id = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, default='pending')
    updated_at = models.DateTimeField(auto_now=True)


class ProviderEvent(models.Model):
    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)


class OrderEvent(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='events')
    version = models.PositiveIntegerField()
    event_type = models.CharField(max_length=40)
    message = models.CharField(max_length=500)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    broadcast_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('version',)
        constraints = [models.UniqueConstraint(fields=['order','version'], name='order_event_version_unique')]


class Notification(models.Model):
    event = models.OneToOneField(OrderEvent, on_delete=models.PROTECT, related_name='notification')
    recipient = models.EmailField()
    status = models.CharField(max_length=20, default='pending')
    attempts = models.PositiveIntegerField(default=0)
    claimed_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    secret_payload = models.TextField(blank=True)


class Refund(models.Model):
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name='refund')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    provider_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, default='pending')
    reason = models.CharField(max_length=500)


class ReturnRequest(models.Model):
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name='return_request')
    reason = models.CharField(max_length=1000)
    status = models.CharField(max_length=20, default='requested')
    admin_reason = models.CharField(max_length=1000, blank=True)
    refund_preference = models.CharField(max_length=20, default='original', choices=[('original','Original payment'),('voucher','Voucher'),('bank','Bank transfer')])
    bank_details_encrypted = models.TextField(blank=True)
    settlement_method = models.CharField(max_length=40, blank=True)
    settlement_reference = models.CharField(max_length=150, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    settled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def bank_details(self):
        if not self.bank_details_encrypted:
            return {}
        import json
        from customers.email_backend import mail_cipher
        return json.loads(mail_cipher().decrypt(self.bank_details_encrypted.encode()).decode())


class DeliveryAttempt(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='delivery_attempts')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    method = models.CharField(max_length=30)
    successful = models.BooleanField()
    reason = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Review(models.Model):
    line = models.OneToOneField(OrderLine, on_delete=models.PROTECT, related_name='review')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='reviews')
    rating = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=150, blank=True)
    text = models.TextField(max_length=5000)
    display_name = models.CharField(max_length=150)
    status = models.CharField(max_length=20, default='pending')
    moderation_reason = models.CharField(max_length=500, blank=True)
    reported = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(rating__gte=1,rating__lte=5), name='review_rating_range')]


class ReviewImage(models.Model):
    review = models.ForeignKey(Review, on_delete=models.PROTECT, related_name='images')
    source = models.CharField(max_length=500)
    variants = models.JSONField(default=dict)

    @property
    def url(self):
        from catalog.media import media_url
        return media_url(self.source)
