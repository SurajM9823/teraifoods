from django import forms
from django.core.exceptions import ValidationError
from .models import Banner, InformationBlock


class BannerForm(forms.ModelForm):
    class Meta:
        model = Banner
        fields = ('title', 'badge', 'description', 'image', 'image_alt', 'button_label', 'destination', 'position', 'is_active')
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def clean_image(self):
        upload = self.cleaned_data.get('image')
        if upload and hasattr(upload, 'content_type'):
            if upload.size > 5 * 1024 * 1024:
                raise ValidationError('Images must be 5 MB or smaller.')
            if upload.image.format not in ('JPEG', 'PNG', 'WEBP'):
                raise ValidationError('Use a JPG, PNG or WebP image.')
            width, height = upload.image.size
            if width * height > 24_000_000 or width < 600 or height < 250:
                raise ValidationError('Use an image at least 600 × 250 pixels and at most 24 megapixels.')
        return upload


class InformationForm(forms.ModelForm):
    class Meta:
        model = InformationBlock
        fields = ('title', 'description', 'is_active')
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}
