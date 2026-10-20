from django import forms
from .models import Product, Subcategory


class ProductForm(forms.ModelForm):
    image = forms.ImageField(required=False, label='Product Image')
    initial_stock = forms.IntegerField(min_value=0, required=False)
    low_stock_threshold = forms.IntegerField(min_value=0, required=False, initial=5)
    class Meta:
        model = Product
        fields = ['name', 'slug', 'sku', 'description', 'category', 'subcategory',
                  'weight', 'weight_unit',
                  'regular_price', 'sale_price', 'new_arrival', 'featured', 'best_seller',
                  'low_stock_threshold', 'is_active', 'is_published', 'is_archived']
        widgets = {'description':forms.Textarea(attrs={'rows':3})}
        labels = {'new_arrival':'New Arrivals', 'featured':'Featured Products', 'best_seller':'Best Sellers'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        category = self.data.get('category') if self.is_bound else self.instance.category_id
        self.fields['subcategory'].queryset = Subcategory.objects.filter(category_id=category) if str(category or '').isdigit() else Subcategory.objects.none()
        if self.instance.pk:
            self.fields.pop('initial_stock')
        placeholders = {
            'regular_price': '0.00',
            'sale_price': '0.00',
        }
        for field_name, ph in placeholders.items():
            if field_name in self.fields:
                self.fields[field_name].widget.attrs['placeholder'] = ph
        if 'regular_price' in self.fields:
            self.fields['regular_price'].widget.attrs['step'] = '0.01'
        if 'sale_price' in self.fields:
            self.fields['sale_price'].widget.attrs['step'] = '0.01'
        if 'weight' in self.fields:
            self.fields['weight'].widget.attrs['step'] = '0.001'

    def clean(self):
        data = super().clean()
        has_image = (
            (self.instance.pk and self.instance.images.filter(is_main=True).exists())
            or bool(self.cleaned_data.get('image'))
        )
        if data.get('is_published') and not has_image:
            self.add_error('is_published', 'Upload a main image before publishing.')
        return data

    def clean_low_stock_threshold(self):
        value = self.cleaned_data.get('low_stock_threshold')
        return value if value is not None else 5


class StockForm(forms.Form):
    quantity = forms.IntegerField(label='Adjustment (+ increase / − decrease)')
    reason = forms.CharField(max_length=500)
    key = forms.CharField(max_length=100, widget=forms.HiddenInput)
