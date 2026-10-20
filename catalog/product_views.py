import uuid
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction, IntegrityError
from django.db.models import Q, F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST
from .models import Product, ProductImage, StockAudit
from .product_forms import ProductForm, StockForm
from .services import adjust_stock, set_main_image, delete_image, reorder_images
from .media import add_image
from .views import permitted


@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['GET', 'HEAD', 'POST'])
def index(request):
    permitted(request, 'view', Product)
    if request.method == 'POST':
        permitted(request, 'change', Product)
        action = request.POST.get('action')
        if action in ('activate', 'deactivate', 'archive'):
            ids = request.POST.getlist('products')
            if len(ids) <= 100 and all(v.isdigit() for v in ids):
                with transaction.atomic():
                    for product in Product.objects.select_for_update().filter(pk__in=ids).order_by('pk'):
                        if action == 'archive':
                            product.is_archived = True
                        else:
                            product.is_active = action == 'activate'
                        product.save()
                messages.success(request, 'Products updated.')
        elif action == 'confirm_stock':
            ids = request.POST.getlist('products')
            if len(ids) <= 100 and all(v.isdigit() for v in ids):
                with transaction.atomic():
                    for product in Product.objects.select_for_update().filter(pk__in=ids).order_by('pk'):
                        key = f'bulk-confirm-{product.pk}-{uuid.uuid4().hex[:8]}'
                        if not product.stock_confirmed:
                            adjust_stock(product.pk, 50, reason='Admin bulk stock confirmation',
                                         actor=request.user, key=key, kind='initial')
                        elif product.stock == 0:
                            adjust_stock(product.pk, 50, reason='Admin bulk restock',
                                         actor=request.user, key=key, kind='manual_increase')
                messages.success(request, 'Selected products stock confirmed (50 units each).')
        return redirect('products:index')
    products = Product.objects.select_related('category', 'subcategory').prefetch_related('images')
    query = request.GET.get('q', '')[:200]
    if query:
        products = products.filter(Q(name__icontains=query) | Q(sku__icontains=query))
    status = request.GET.get('status')
    if status in ('active', 'inactive'):
        products = products.filter(is_active=status == 'active')
    elif status == 'low':
        products = products.filter(stock__lte=F('low_stock_threshold'))
    if request.GET.get('category', '').isdigit():
        products = products.filter(category_id=request.GET['category'])
    sort = request.GET.get('sort', 'name')
    if sort not in ('name', '-name', 'stock', '-stock', 'regular_price', '-regular_price'):
        sort = 'name'
    from .models import Category
    return render(request, 'catalog/products/index.html', dict(active_page='products',
        page=Paginator(products.order_by(sort, 'pk'), 20).get_page(request.GET.get('page')),
        query=query, categories=Category.objects.all()))


@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['GET', 'HEAD', 'POST'])
def edit(request, pk=None):
    permitted(request, 'change' if pk else 'add', Product)
    with transaction.atomic():
        product = get_object_or_404(Product.objects.select_for_update(), pk=pk) if pk else Product()
        form = ProductForm(request.POST if request.method == 'POST' else None,
                           request.FILES if request.method == 'POST' else None,
                           instance=product)
        if request.method == 'POST' and form.is_valid():
            try:
                with transaction.atomic():
                    product = form.save()
                    if form.cleaned_data.get('image'):
                        from .media import add_image
                        add_image(product.pk, form.cleaned_data['image'], main=True)
                    if not pk and form.cleaned_data.get('initial_stock') is not None:
                        adjust_stock(product.pk, form.cleaned_data['initial_stock'], reason='Initial stock on creation',
                                     actor=request.user, key=uuid.uuid4().hex, kind='initial')
            except IntegrityError:
                form.add_error(None, 'Another product uses that slug. Refresh and try again.')
            except ValidationError as exc:
                form.add_error(None, ' '.join(exc.messages))
            else:
                messages.success(request, 'Product saved.')
                return redirect('products:edit', pk=product.pk)
    from .models import Subcategory
    return render(request, 'catalog/products/edit.html', dict(active_page='products',
        form=form, product=product, stock_form=StockForm(initial={'key':uuid.uuid4().hex}),
        subcategories=list(Subcategory.objects.values('id','name','category_id')),
        history=Paginator(product.stock_history.select_related('actor'), 50).get_page(request.GET.get('history_page')) if pk else []))


@never_cache
@staff_member_required(login_url='/admin/login')
@require_POST
def stock(request, pk):
    permitted(request, 'change', Product)
    product = get_object_or_404(Product, pk=pk)
    form = StockForm(request.POST)
    if form.is_valid():
        try:
            quantity = form.cleaned_data['quantity']
            previous = StockAudit.objects.filter(idempotency_key=form.cleaned_data['key']).first()
            adjust_stock(pk, quantity, actor=request.user, reason=form.cleaned_data['reason'],
                         key=form.cleaned_data['key'], kind=previous.adjustment_type if previous else ('initial' if not product.stock_confirmed else ('manual_increase' if quantity >= 0 else 'manual_decrease')))
        except ValidationError as exc:
            messages.error(request, ' '.join(exc.messages))
        else:
            messages.success(request, 'Stock adjustment recorded.')
    else:
        messages.error(request, 'Enter a whole-number adjustment and a reason.')
    return redirect('products:edit', pk=pk)


@never_cache
@staff_member_required(login_url='/admin/login')
@require_POST
def images(request, pk):
    permitted(request, 'change', Product)
    get_object_or_404(Product, pk=pk)
    try:
        action = request.POST.get('action')
        if action == 'upload':
            if 'image' not in request.FILES:
                raise ValidationError('Choose an image.')
            add_image(pk, request.FILES['image'], main=request.POST.get('main') == 'on')
        elif action == 'main':
            set_main_image(pk, request.POST.get('image_id'))
        elif action == 'delete':
            delete_image(pk, request.POST.get('image_id'), request.POST.get('replacement_id'))
        elif action == 'reorder':
            reorder_images(pk, [int(value) for value in request.POST.get('order', '').split(',')])
        else:
            raise ValidationError('Invalid image action.')
    except (ValidationError, ValueError, ProductImage.DoesNotExist) as exc:
        messages.error(request, ' '.join(getattr(exc, 'messages', ['Invalid image selection.'])))
    else:
        messages.success(request, 'Images updated.')
    return redirect('products:edit', pk=pk)
