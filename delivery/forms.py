from decimal import Decimal
from django import forms
from .models import DeliveryPolicy, WeightBand


class WeightBandForm(forms.ModelForm):
    upper_weight = forms.DecimalField(min_value=Decimal('0.001'), max_digits=10, decimal_places=3, label='Up to weight (inclusive)')
    unit = forms.ChoiceField(choices=[('g','gm (grams)'), ('kg','kg (kilograms)')], initial='g')

    class Meta:
        model = WeightBand
        fields = ['upper_weight', 'unit', 'charge', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial['upper_weight'] = self.instance.max_weight_grams
            self.initial['unit'] = 'g'

    def clean(self):
        data = super().clean()
        if data.get('upper_weight') is not None and data.get('unit'):
            grams = data['upper_weight'] * (1000 if data['unit'] == 'kg' else 1)
            self.instance.max_weight_grams = grams
            if WeightBand.objects.filter(max_weight_grams=grams).exclude(pk=self.instance.pk).exists():
                self.add_error('upper_weight', 'A band with this upper weight already exists.')
        return data


class DeliveryPolicyForm(forms.ModelForm):
    class Meta:
        model = DeliveryPolicy
        fields = ['minimum_days', 'maximum_days']

    def clean(self):
        data = super().clean()
        if data.get('minimum_days') and data.get('maximum_days') and data['maximum_days'] < data['minimum_days']:
            self.add_error('maximum_days', 'Maximum delivery days must be at least the minimum.')
        return data
