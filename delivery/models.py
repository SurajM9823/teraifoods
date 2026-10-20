from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models


class DeliveryPolicy(models.Model):
    """One UK-wide policy; day counts are an estimate, not a guaranteed ETA."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    minimum_days = models.PositiveSmallIntegerField(default=2, validators=[MinValueValidator(1)])
    maximum_days = models.PositiveSmallIntegerField(default=4, validators=[MinValueValidator(1)])
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'delivery policy'
        constraints = [
            models.CheckConstraint(condition=models.Q(id=1), name='delivery_policy_singleton'),
            models.CheckConstraint(condition=models.Q(minimum_days__gte=1) & models.Q(maximum_days__gte=models.F('minimum_days')), name='delivery_days_ordered'),
        ]

    def __str__(self):
        return f'Whole UK · estimated {self.minimum_days}–{self.maximum_days} days'


class WeightBand(models.Model):
    max_weight_grams = models.DecimalField(max_digits=13, decimal_places=3, unique=True,
        validators=[MinValueValidator(Decimal('0.001'))],
        help_text='Inclusive upper limit. The smallest active band covering the basket is used.')
    charge = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('max_weight_grams', 'pk')
        constraints = [
            models.CheckConstraint(condition=models.Q(max_weight_grams__gt=0), name='delivery_band_positive_weight'),
            models.CheckConstraint(condition=models.Q(charge__gte=0), name='delivery_charge_nonnegative'),
        ]

    def __str__(self):
        return f'Up to {self.max_weight_grams.normalize():f} gm — £{self.charge}'
