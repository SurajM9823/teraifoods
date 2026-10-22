from django import forms
from django.core.exceptions import ValidationError
from .models import Banner, InformationBlock, ContactSettings, FAQItem, ContactHub, ContactInquiry


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


class ContactSettingsForm(forms.ModelForm):
    class Meta:
        model = ContactSettings
        fields = (
            'phone', 'operating_hours',
            'whatsapp_number', 'whatsapp_title', 'whatsapp_subtitle',
            'support_email', 'support_email_sla', 'support_email_subtext',
            'wholesale_email', 'wholesale_email_subtext',
            'office_title', 'office_address',
            'social_heading', 'social_badge', 'social_text',
            'facebook_url', 'twitter_url', 'instagram_url', 'linkedin_url',
            'map_badge', 'map_subtitle',
        )
        widgets = {
            'office_address': forms.TextInput(attrs={'placeholder': 'Full UK Depot Address'}),
            'social_text': forms.Textarea(attrs={'rows': 2}),
            'map_subtitle': forms.Textarea(attrs={'rows': 2}),
        }


class FAQItemForm(forms.ModelForm):
    class Meta:
        model = FAQItem
        fields = ('question', 'answer', 'order', 'is_active')
        widgets = {
            'question': forms.TextInput(attrs={'placeholder': 'e.g. How does cold-chain delivery work in the UK?'}),
            'answer': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Detailed customer-facing answer...'}),
        }


class ContactHubForm(forms.ModelForm):
    class Meta:
        model = ContactHub
        fields = ('name', 'tag', 'legend', 'description', 'latitude', 'longitude', 'order', 'is_active')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }


class ContactInquiryForm(forms.ModelForm):
    class Meta:
        model = ContactInquiry
        fields = ('status', 'admin_notes')
        widgets = {
            'admin_notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Internal staff notes...'}),
        }
