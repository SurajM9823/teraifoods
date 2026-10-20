from decimal import Decimal
from django.core.exceptions import ValidationError
from .models import DeliveryPolicy, WeightBand


def quote_delivery(products, quantities, *, country='GB', lock=False):
    if country not in ('GB', 'UK'):
        raise ValidationError('Delivery is available throughout the United Kingdom only.')
    weight = sum((product.weight_grams * quantities[product.pk] for product in products), Decimal('0'))
    if weight <= 0:
        raise ValidationError('A positive basket weight is required.')
    bands = WeightBand.objects.filter(is_active=True, max_weight_grams__gte=weight)
    if lock:
        bands = bands.select_for_update()
    band = bands.order_by('max_weight_grams', 'pk').first()
    if band is None:
        raise ValidationError('No delivery charge is configured for this basket weight. Please contact the store.')
    policies = DeliveryPolicy.objects.select_for_update() if lock else DeliveryPolicy.objects
    policy = policies.filter(pk=1).first()
    return dict(weight_grams=weight, charge=band.charge,
                minimum_days=policy.minimum_days if policy else 2,
                maximum_days=policy.maximum_days if policy else 4,
                band_id=band.pk, country='GB')
