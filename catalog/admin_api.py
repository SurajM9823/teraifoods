"""Session-authenticated staff APIs; Django CSRF protection remains enabled."""
import json
import uuid
from functools import wraps
from django.core.exceptions import ValidationError, PermissionDenied
from django.http import Http404
from django.core.paginator import Paginator
from django.db import transaction, IntegrityError
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .models import Product, ProductImage, Category, Subcategory
from .product_forms import ProductForm
from .forms import CategoryForm, SubcategoryForm
from .services import adjust_stock, set_main_image, delete_image, reorder_images
from .media import add_image


def staff_api(view):
    @wraps(view)
    @never_cache
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'errors':['Authentication required.']}, status=401)
        if not request.user.is_active or not request.user.is_staff:
            return JsonResponse({'errors':['Staff access required.']}, status=403)
        try:
            return view(request, *args, **kwargs)
        except ValidationError as exc:
            return JsonResponse({'errors':getattr(exc, 'message_dict', exc.messages)}, status=400)
        except PermissionDenied:
            return JsonResponse({'errors':['Permission denied.']}, status=403)
        except Http404:
            return JsonResponse({'errors':['Not found.']}, status=404)
        except (ValueError, TypeError, json.JSONDecodeError):
            return JsonResponse({'errors':['Invalid request.']}, status=400)
        except IntegrityError:
            return JsonResponse({'errors':['A conflicting update occurred. Refresh and retry.']}, status=409)
    return wrapped


def permission(request, action, model):
    if not request.user.has_perm(f'catalog.{action}_{model._meta.model_name}'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied


def body(request):
    data = json.loads(request.body)
    if not isinstance(data, dict):
        raise ValidationError('Expected a JSON object.')
    return data


def product_data(product):
    return dict(id=product.pk, name=product.name, slug=product.slug, category_id=product.category_id,
        subcategory_id=product.subcategory_id, regular_price=str(product.regular_price),
        sale_price=str(product.sale_price) if product.sale_price is not None else None,
        is_active=product.is_active, is_published=product.is_published, is_archived=product.is_archived,
        new_arrival=product.new_arrival, featured=product.featured, best_seller=product.best_seller,
        stock=product.stock if product.stock_confirmed else None, low_stock_threshold=product.low_stock_threshold,
        images=[dict(id=i.pk, url=i.url, main=i.is_main, position=i.position) for i in product.images.all()])


@staff_api
@require_http_methods(['GET', 'POST', 'PATCH', 'DELETE'])
def products(request, pk=None):
    action = 'view' if request.method == 'GET' else 'add' if pk is None else 'change'
    permission(request, action, Product)
    if request.method == 'GET':
        if pk:
            return JsonResponse(product_data(get_object_or_404(Product.objects.prefetch_related('images'), pk=pk)))
        queryset = Product.objects.prefetch_related('images').order_by('pk')
        if request.GET.get('q'):
            queryset = queryset.filter(name__icontains=request.GET['q'][:200])
        page = Paginator(queryset, 20).get_page(request.GET.get('page'))
        return JsonResponse({'products':[product_data(p) for p in page], 'total':page.paginator.count, 'has_more':page.has_next()})
    if request.method != 'POST' and not pk:
        raise ValidationError('Select a product.')
    with transaction.atomic():
        product = get_object_or_404(Product.objects.select_for_update(), pk=pk) if pk else Product()
        if request.method == 'DELETE':
            product.is_archived = True
            product.save()
            return JsonResponse(product_data(product))
        incoming = body(request)
        fields = ProductForm.Meta.fields
        values = {name:getattr(product, name + '_id' if name in ('category','subcategory') else name) for name in fields} if pk else {}
        values.update({name:value for name,value in incoming.items() if name in fields})
        if 'category' in incoming and 'subcategory' not in incoming:
            values['subcategory'] = None
        form = ProductForm(values, instance=product)
        if not form.is_valid():
            return JsonResponse({'errors':form.errors.get_json_data()}, status=400)
        product = form.save()
        return JsonResponse(product_data(product), status=200 if pk else 201)


@staff_api
@require_http_methods(['GET', 'POST'])
def stock(request, pk):
    permission(request, 'view' if request.method == 'GET' else 'change', Product)
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'GET':
        page = Paginator(product.stock_history.all(), 50).get_page(request.GET.get('page'))
        return JsonResponse({'history':list(page.object_list.values('id','previous_quantity','adjustment',
            'new_quantity','adjustment_type','reason','actor_id','created_at','reference')), 'has_more':page.has_next()})
    data = body(request)
    audit = adjust_stock(pk, data.get('quantity'), actor=request.user, reason=data.get('reason', ''),
        key=request.headers.get('Idempotency-Key', ''), kind=data.get('type', 'correction'), reference=data.get('reference',''))
    return JsonResponse({'id':audit.pk, 'previous_quantity':audit.previous_quantity, 'new_quantity':audit.new_quantity})


@staff_api
@require_http_methods(['POST'])
def images(request, pk):
    permission(request, 'change', Product)
    get_object_or_404(Product, pk=pk)
    if request.content_type == 'multipart/form-data':
        if 'image' not in request.FILES:
            raise ValidationError('Choose an image.')
        image = add_image(pk, request.FILES['image'], main=request.POST.get('main') == 'true')
        return JsonResponse({'id':image.pk, 'url':image.url}, status=201)
    data = body(request)
    if data.get('action') in ('main','delete'):
        get_object_or_404(ProductImage, pk=data.get('image_id'), product_id=pk)
    if data.get('action') == 'main':
        set_main_image(pk, data.get('image_id'))
    elif data.get('action') == 'delete':
        if data.get('replacement_id'):
            get_object_or_404(ProductImage, pk=data['replacement_id'], product_id=pk)
        delete_image(pk, data.get('image_id'), data.get('replacement_id'))
    elif data.get('action') == 'reorder':
        reorder_images(pk, data.get('image_ids', []))
    else:
        raise ValidationError('Choose upload, main, delete or reorder.')
    return JsonResponse({'ok':True})


@staff_api
@require_http_methods(['GET', 'POST', 'PATCH', 'DELETE'])
def categories(request, kind, pk=None):
    if kind not in ('categories', 'subcategories'):
        raise Http404
    model, form_class = (Category, CategoryForm) if kind == 'categories' else (Subcategory, SubcategoryForm)
    permission(request, 'view' if request.method == 'GET' else 'delete' if request.method == 'DELETE' else 'change' if pk else 'add', model)
    if request.method == 'GET':
        queryset = model.objects.all()
        if pk:
            get_object_or_404(queryset, pk=pk)
            queryset = queryset.filter(pk=pk)
        return JsonResponse({'items':list(queryset.values())})
    with transaction.atomic():
        instance = get_object_or_404(model.objects.select_for_update(), pk=pk) if pk else model()
        if request.method == 'DELETE':
            if not pk:
                raise ValidationError('Select a category.')
            try:
                instance.delete()
            except ProtectedError:
                raise ValidationError('This category is in use. Reassign its products or deactivate it.')
            return JsonResponse({'ok':True})
        from django.forms.models import model_to_dict
        values = model_to_dict(instance)
        values.update(body(request))
        form = form_class(values, instance=instance)
        if not form.is_valid():
            return JsonResponse({'errors':form.errors.get_json_data()}, status=400)
        result = form.save()
        return JsonResponse({'id':result.pk}, status=200 if pk else 201)
