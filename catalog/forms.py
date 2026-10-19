from django import forms
from django.utils.text import slugify
from .models import Category, Subcategory


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ('name', 'slug', 'description', 'icon', 'position', 'is_active')
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('slug'):
            cleaned['slug'] = slugify(cleaned.get('name', ''), allow_unicode=True)[:120]
            if not cleaned['slug']:
                self.add_error('slug', 'Enter a slug with letters or numbers.')
        return cleaned


class SubcategoryForm(CategoryForm):
    class Meta(CategoryForm.Meta):
        model = Subcategory
        fields = ('category',) + CategoryForm.Meta.fields
