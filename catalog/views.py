from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.http import Http404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .forms import CategoryForm, SubcategoryForm
from .models import Category, Subcategory


def permitted(request, action, model):
    if not request.user.has_perm(f'catalog.{action}_{model._meta.model_name}'):
        raise PermissionDenied


@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['GET', 'HEAD'])
def index(request):
    permitted(request, 'view', Category)
    query = request.GET.get('q', '').strip()[:100]
    status = request.GET.get('status', '')
    categories = Category.objects.all()
    if query:
        condition = Q(name__icontains=query) | Q(slug__icontains=query)
        if request.user.has_perm('catalog.view_subcategory'):
            condition |= Q(subcategories__name__icontains=query)
        categories = categories.filter(condition).distinct()
    if status in ('active', 'inactive'):
        categories = categories.filter(is_active=status == 'active')
    categories = categories.prefetch_related('subcategories')
    page = Paginator(categories, 20).get_page(request.GET.get('page'))
    return render(request, 'catalog/index.html', dict(
        active_page='categories', page=page, query=query, status=status,
        total=Category.objects.count(), active=Category.objects.filter(is_active=True).count(),
    ))


@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['GET', 'HEAD', 'POST'])
def edit(request, kind, pk=None):
    model, form_class = (Category, CategoryForm) if kind == 'category' else (Subcategory, SubcategoryForm)
    permitted(request, 'change' if pk else 'add', model)
    instance = get_object_or_404(model, pk=pk) if pk else None
    initial = {}
    if kind == 'subcategory' and not pk and request.GET.get('parent'):
        if not request.GET['parent'].isascii() or not request.GET['parent'].isdigit():
            raise Http404('Category not found')
        initial['category'] = get_object_or_404(Category, pk=request.GET['parent'])
    form = form_class(request.POST if request.method == 'POST' else None, instance=instance, initial=initial)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                form.save()
        except IntegrityError:
            form.add_error(None, 'That name or slug is already in use, or the parent changed. Please review and save again.')
        else:
            messages.success(request, f'{kind.capitalize()} saved.')
            return redirect('catalog:index')
    return render(request, 'catalog/edit.html', dict(
        active_page='categories', form=form, kind=kind, editing=bool(pk),
        no_parents=kind == 'subcategory' and not Category.objects.exists(),
    ))


@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['POST'])
def status(request, kind, pk):
    model = Category if kind == 'category' else Subcategory
    permitted(request, 'change', model)
    with transaction.atomic():
        item = get_object_or_404(model.objects.select_for_update(), pk=pk)
        # Explicit target makes repeated form submissions idempotent.
        value = request.POST.get('active')
        if value not in ('true', 'false'):
            from django.http import HttpResponseBadRequest
            return HttpResponseBadRequest('Choose active or inactive.')
        item.is_active = value == 'true'
        item.save(update_fields=['is_active', 'updated_at'])
    messages.success(request, f'{item.name} is now {"active" if item.is_active else "inactive"}.')
    return redirect('catalog:index')


@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['GET', 'HEAD', 'POST'])
def delete(request, kind, pk):
    model = Category if kind == 'category' else Subcategory
    permitted(request, 'delete', model)
    item = get_object_or_404(model, pk=pk)
    blocked = kind == 'category' and item.subcategories.exists()
    if request.method == 'POST':
        try:
            with transaction.atomic():
                item.delete()
        except ProtectedError:
            blocked = True
            messages.error(request, 'Move or delete the subcategories first, or deactivate this category instead.')
        else:
            messages.success(request, f'{kind.capitalize()} deleted.')
            return redirect('catalog:index')
    return render(request, 'catalog/delete.html', dict(
        active_page='categories', item=item, kind=kind, blocked=blocked,
    ))
