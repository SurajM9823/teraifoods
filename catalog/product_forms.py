from django import forms
from .models import Product, Subcategory


class ProductForm(forms.ModelForm):
    initial_stock = forms.IntegerField(min_value=0, required=False,
        help_text='Leave blank if stock has not been counted. Zero confirms no stock.')
    class Meta:
        model = Product
        fields = ['name', 'slug', 'sku', 'description', 'category', 'subcategory',
                  'regular_price', 'sale_price', 'new_arrival', 'featured', 'best_seller',
                  'low_stock_threshold', 'is_active', 'is_published', 'is_archived']
        widgets = {'description':forms.Textarea(attrs={'rows':4})}
        labels = {'new_arrival':'New Arrivals', 'featured':'Featured Products', 'best_seller':'Best Sellers'}
        help_texts = {'is_published':'Upload a main image before publishing.',
                      'sale_price':'Required for Featured Products; must be below the regular price.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        category = self.data.get('category') if self.is_bound else self.instance.category_id
        self.fields['subcategory'].queryset = Subcategory.objects.filter(category_id=category) if str(category or '').isdigit() else Subcategory.objects.none()
        if self.instance.pk:
            self.fields.pop('initial_stock')

    def clean(self):
        data = super().clean()
        if data.get('is_published') and (not self.instance.pk or not self.instance.images.filter(is_main=True).exists()):
            self.add_error('is_published', 'Save a draft and upload a main image before publishing.')
        return data


class StockForm(forms.Form):
    quantity = forms.IntegerField(label='Adjustment (+ increase / − decrease)')
    reason = forms.CharField(max_length=500)
    key = forms.CharField(max_length=100, widget=forms.HiddenInput)
