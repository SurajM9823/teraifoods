"""Channel boundary for existing website financial/inventory operations."""
from django.core.exceptions import ValidationError


def require_website_order(order):
    if order.sales_channel != 'website' or order.payment_method == 'shopify':
        raise ValidationError('Manage Shopify payments, cancellations, refunds and returns in Shopify.')
