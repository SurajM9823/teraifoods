from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .forms import BannerForm, InformationForm
from .models import Banner, InformationBlock


@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['GET', 'HEAD'])
def dashboard(request):
    if not request.user.has_perms(('cms.view_banner', 'cms.view_informationblock')):
        raise PermissionDenied
    return render(request, 'cms/dashboard.html', {
        'active_page': 'cms', 'banners': Banner.objects.all(),
        'information': InformationBlock.objects.all(),
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
        messages.success(request, 'Website content saved.')
        return redirect('cms:dashboard')
    return render(request, 'cms/edit.html', {'form': form, 'kind': kind, 'active_page': 'cms'})


@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['POST'])
def delete_banner(request, pk):
    if not request.user.has_perm('cms.delete_banner'):
        raise PermissionDenied
    get_object_or_404(Banner, pk=pk).delete()
    messages.success(request, 'Banner deleted.')
    return redirect('cms:dashboard')
