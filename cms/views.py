from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from .forms import (
    BannerForm, InformationForm, ContactSettingsForm,
    FAQItemForm, ContactHubForm, ContactInquiryForm
)
from .models import (
    Banner, InformationBlock, ContactSettings,
    FAQItem, ContactHub, ContactInquiry
)


@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['GET', 'HEAD'])
def dashboard(request):
    if not request.user.has_perms(('cms.view_banner', 'cms.view_informationblock')):
        raise PermissionDenied
    return render(request, 'cms/dashboard.html', {
        'active_page': 'cms',
        'banners': Banner.objects.all().order_by('position', 'id'),
        'information': InformationBlock.objects.all().order_by('slot'),
    })


@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['GET', 'HEAD', 'POST'])
def edit(request, kind, pk=None):
    model, form_class = (Banner, BannerForm) if kind == 'banner' else (InformationBlock, InformationForm)
    instance = get_object_or_404(model, pk=pk) if pk else None
    action = 'change' if instance else 'add'
    if not request.user.has_perm(f'cms.{action}_{model._meta.model_name}'):
        raise PermissionDenied
    form = form_class(request.POST or None, request.FILES or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            form.save()
        messages.success(request, f"{'Banner' if kind == 'banner' else 'Information block'} saved successfully.")
        return redirect('cms:dashboard')
    return render(request, 'cms/edit.html', {'form': form, 'kind': kind, 'instance': instance, 'active_page': 'cms'})


@never_cache
@staff_member_required(login_url='/admin/login')
@require_POST
def delete_banner(request, pk):
    if not request.user.has_perm('cms.delete_banner'):
        raise PermissionDenied
    get_object_or_404(Banner, pk=pk).delete()
    messages.success(request, 'Banner deleted.')
    return redirect('cms:dashboard')


# --- Contact Settings & Social Links ---
@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['GET', 'HEAD', 'POST'])
def contact_settings(request):
    if not request.user.has_perm('cms.view_contactsettings'):
        raise PermissionDenied
    settings_obj = ContactSettings.get_solo()
    if request.method == 'POST':
        if not request.user.has_perm('cms.change_contactsettings'):
            raise PermissionDenied
        form = ContactSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Contact settings and social channels updated.')
            return redirect('cms:contact-settings')
    else:
        form = ContactSettingsForm(instance=settings_obj)
    return render(request, 'cms/contact_settings.html', {
        'form': form,
        'settings_obj': settings_obj,
        'active_page': 'contact-settings',
    })


# --- FAQs Management ---
@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['GET', 'HEAD'])
def faqs_index(request):
    if not request.user.has_perm('cms.view_faqitem'):
        raise PermissionDenied
    faqs = FAQItem.objects.all().order_by('order', 'id')
    query = request.GET.get('q', '').strip()
    if query:
        faqs = faqs.filter(Q(question__icontains=query) | Q(answer__icontains=query))
    return render(request, 'cms/faqs_index.html', {
        'faqs': faqs,
        'query': query,
        'total': FAQItem.objects.count(),
        'active_count': FAQItem.objects.filter(is_active=True).count(),
        'active_page': 'faqs',
    })


@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['GET', 'HEAD', 'POST'])
def faq_edit(request, pk=None):
    action = 'change' if pk else 'add'
    if not request.user.has_perm(f'cms.{action}_faqitem'):
        raise PermissionDenied
    instance = get_object_or_404(FAQItem, pk=pk) if pk else None
    form = FAQItemForm(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'FAQ saved.')
        return redirect('cms:faqs-index')
    return render(request, 'cms/faq_edit.html', {
        'form': form,
        'instance': instance,
        'active_page': 'faqs',
    })


@never_cache
@staff_member_required(login_url='/admin/login')
@require_POST
def faq_delete(request, pk):
    if not request.user.has_perm('cms.delete_faqitem'):
        raise PermissionDenied
    get_object_or_404(FAQItem, pk=pk).delete()
    messages.success(request, 'FAQ removed.')
    return redirect('cms:faqs-index')


# --- Contact Map Hubs ---
@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['GET', 'HEAD'])
def hubs_index(request):
    if not request.user.has_perm('cms.view_contacthub'):
        raise PermissionDenied
    hubs = ContactHub.objects.all().order_by('order', 'id')
    return render(request, 'cms/hubs_index.html', {
        'hubs': hubs,
        'total': hubs.count(),
        'active_page': 'hubs',
    })


@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['GET', 'HEAD', 'POST'])
def hub_edit(request, pk=None):
    action = 'change' if pk else 'add'
    if not request.user.has_perm(f'cms.{action}_contacthub'):
        raise PermissionDenied
    instance = get_object_or_404(ContactHub, pk=pk) if pk else None
    form = ContactHubForm(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Map Hub saved.')
        return redirect('cms:hubs-index')
    return render(request, 'cms/hub_edit.html', {
        'form': form,
        'instance': instance,
        'active_page': 'hubs',
    })


@never_cache
@staff_member_required(login_url='/admin/login')
@require_POST
def hub_delete(request, pk):
    if not request.user.has_perm('cms.delete_contacthub'):
        raise PermissionDenied
    get_object_or_404(ContactHub, pk=pk).delete()
    messages.success(request, 'Hub deleted.')
    return redirect('cms:hubs-index')


# --- Support Enquiries ---
@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['GET', 'HEAD'])
def inquiries_index(request):
    if not request.user.has_perm('cms.view_contactinquiry'):
        raise PermissionDenied
    rows = ContactInquiry.objects.all().order_by('-created_at')
    status_filter = request.GET.get('status', '').strip()
    if status_filter:
        rows = rows.filter(status=status_filter)
    query = request.GET.get('q', '').strip()
    if query:
        rows = rows.filter(Q(name__icontains=query) | Q(email__icontains=query) | Q(message__icontains=query))
    page = Paginator(rows, 25).get_page(request.GET.get('page'))
    return render(request, 'cms/inquiries_index.html', {
        'page': page,
        'query': query,
        'status_filter': status_filter,
        'total': ContactInquiry.objects.count(),
        'new_count': ContactInquiry.objects.filter(status='new').count(),
        'active_page': 'inquiries',
    })


@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['GET', 'HEAD', 'POST'])
def inquiry_detail(request, pk):
    if not request.user.has_perm('cms.view_contactinquiry'):
        raise PermissionDenied
    inquiry = get_object_or_404(ContactInquiry, pk=pk)
    form = ContactInquiryForm(request.POST or None, instance=inquiry)
    if request.method == 'POST':
        if not request.user.has_perm('cms.change_contactinquiry'):
            raise PermissionDenied
        if form.is_valid():
            form.save()
            messages.success(request, f'Enquiry #{inquiry.pk} status updated.')
            return redirect('cms:inquiry-detail', pk=pk)
    return render(request, 'cms/inquiry_detail.html', {
        'inquiry': inquiry,
        'form': form,
        'active_page': 'inquiries',
    })
