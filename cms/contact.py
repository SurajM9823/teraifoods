import re
from django import forms
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import ContactInquiry


class InquiryForm(forms.ModelForm):
    topic = forms.ChoiceField(choices=ContactInquiry.TOPIC_CHOICES)
    message = forms.CharField(max_length=10000)

    class Meta:
        model = ContactInquiry
        fields = ('name', 'email', 'phone', 'topic', 'message')

    def clean_phone(self):
        value = self.cleaned_data['phone']
        if value and not re.fullmatch(r'(?:\+44|0044|0)\d{9,10}', re.sub(r'[\s().-]', '', value)):
            raise forms.ValidationError('Enter a valid UK phone number.')
        return value


@require_POST
def submit(request):
    form = InquiryForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errors': form.errors}, status=400)
    key = 'contact-inquiry:' + request.META.get('REMOTE_ADDR', '')
    if not cache.add(key, True, timeout=20):
        return JsonResponse({'errors': {'form': ['Please wait a moment before sending another enquiry.']}}, status=429)
    inquiry = form.save()
    return JsonResponse({'received': True, 'reference': inquiry.pk}, status=201)
