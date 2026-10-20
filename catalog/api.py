import hashlib
import json
from decimal import Decimal, InvalidOperation
from django.core import signing
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.models import Q, F, Max, Count
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control, never_cache
from django.views.decorators.http import require_GET, require_POST
from .content import CACHE_ERRORS
from .models import Product, ProductImage, Category, Subcategory
from .services import reserve_order


class CatalogChanged(ValidationError):
    pass


def public_products():
    return Product.objects.filter(is_active=True, is_published=True, is_archived=False,
        category__is_active=True).filter(Q(subcategory__isnull=True) | Q(subcategory__is_active=True)).select_related(
        'category', 'subcategory').prefetch_related('images').annotate(selling_price=Coalesce('sale_price', 'regular_price'))


def serialize(product):
    return dict(id=product.pk, name=product.name, slug=product.slug, description=product.description,
        category=product.category.slug, category_key=product.category.legacy_key or product.category.slug,
        subcategory=product.subcategory.slug if product.subcategory_id else None,
        regular_price=str(product.regular_price), sale_price=str(product.sale_price) if product.sale_price is not None else None,
        price=str(product.price), discount=product.discount_percent, available=product.available,
        stock=product.stock if product.stock_confirmed else None,
        sections=[key for key, value in [('new_arrival',product.new_arrival),('featured',product.featured),('best_seller',product.best_seller),('for_you',True)] if value],
        image=product.image_url, url=f'/product-detail/?product={product.slug}',
        images=[dict(id=image.pk, url=image.url, avif=image.avif_srcset, webp=image.webp_srcset,
                     main=image.is_main, alt=image.alt, width=image.width, height=image.height) for image in product.images.all()])


def paginate(params):
    from .models import CatalogRevision
    revision, _ = CatalogRevision.objects.get_or_create(pk=1)
    queryset = public_products()
    category, subcategory = params.get('category'), params.get('subcategory')
    if category:
        queryset = queryset.filter(category__slug=category)
    if subcategory:
        queryset = queryset.filter(subcategory__slug=subcategory)
    query = params.get('q', params.get('s', '')).strip()[:200]
    if query:
        queryset = queryset.filter(Q(name__icontains=query) | Q(description__icontains=query) | Q(sku__icontains=query))
    section = params.get('section', '')
    if section in ('new_arrival', 'featured', 'best_seller'):
        queryset = queryset.filter(**{section:True})
    elif section not in ('', 'for_you'):
        raise ValidationError('Invalid product section.')
    try:
        limit = min(48, max(1, int(params.get('limit', 12))))
        for key, operator in [('min_price','gte'), ('max_price','lte')]:
            if params.get(key):
                value = Decimal(params[key])
                if not value.is_finite() or not 0 <= value <= Decimal('9999999999.99'):
                    raise ValueError()
                queryset = queryset.filter(**{f'selling_price__{operator}':value})
    except (ValueError, InvalidOperation, TypeError):
        raise ValidationError('Invalid page size or price filter.')
    sort = params.get('sort', '')
    queryset = queryset.annotate(sort_rating=Coalesce('rating', Decimal('0.00')))
    field = {'price-asc':'selling_price', 'price-desc':'-selling_price', 'name':'name', 'newest':'-id', 'rating':'-sort_rating'}.get(sort, 'display_order')
    fingerprint = hashlib.sha256(json.dumps({k:params.get(k, '') for k in ('category','subcategory','q','s','section','min_price','max_price','sort','limit')}, sort_keys=True).encode()).hexdigest()
    count = queryset.count()
    if params.get('cursor'):
        try:
            cursor = signing.loads(params['cursor'], salt='catalog-page', max_age=86400)
            if cursor['filter'] != fingerprint:
                raise ValueError()
            if cursor.get('revision') != revision.version:
                raise CatalogChanged('The catalog changed. Reload the first page.')
            last_id, value = int(cursor['id']), cursor['value']
            ascending = not field.startswith('-')
            name = field.lstrip('-')
            op = 'gt' if ascending else 'lt'
            if name == 'id':
                queryset = queryset.filter(**{f'id__{op}': last_id})
            else:
                queryset = queryset.filter(Q(**{f'{name}__{op}':value}) | (Q(**{name:value}) & Q(id__gt=last_id)))
        except (signing.BadSignature, KeyError, ValueError, TypeError):
            raise ValidationError('Invalid or expired pagination cursor.')
    rows = list(queryset.order_by(field, 'id')[:limit + 1])
    more, rows = len(rows) > limit, rows[:limit]
    next_cursor = None
    if more:
        last = rows[-1]
        next_cursor = signing.dumps(dict(filter=fingerprint, revision=revision.version, id=last.pk, value=str(getattr(last, field.lstrip('-')))), salt='catalog-page')
    return rows, dict(next_cursor=next_cursor, has_more=more, total=count)


def cached_payload(request, loader):
    # Database revision survives Redis outages/restarts; stale generations cannot
    # reappear after an invalidation failed while Redis was offline.
    from .models import CatalogRevision
    revision, _ = CatalogRevision.objects.get_or_create(pk=1)
    key = 'catalog:public:' + str(revision.version) + ':' + hashlib.sha256(request.get_full_path().encode()).hexdigest()
    try:
        payload = cache.get(key)
        if payload is not None:
            return payload
    except CACHE_ERRORS:
        pass
    payload = loader()
    try:
        cache.set(key, payload, 60)
    except CACHE_ERRORS:
        pass
    return payload


@require_GET
@cache_control(public=True, max_age=0, must_revalidate=True)
def listing(request):
    def load():
        rows, info = paginate(request.GET)
        for product in rows:
            product.card_template = product.metadata.get('cards', {}).get('shop_0', 'catalog/storefront/card_shop_0_0.html')
            if not product.card_template.startswith('catalog/storefront/card_') or '..' in product.card_template:
                product.card_template = 'catalog/storefront/card_shop_0_0.html'
        from django.template.loader import render_to_string
        return dict(products=[serialize(p) for p in rows], html=render_to_string('catalog/storefront/shop_cards.html', {'products':rows}), **info)
    try:
        payload = cached_payload(request, load)
    except CatalogChanged as exc:
        return JsonResponse({'errors':exc.messages, 'restart':True}, status=409)
    except ValidationError as exc:
        return JsonResponse({'errors':exc.messages}, status=400)
    response = JsonResponse(payload)
    response['ETag'] = '"' + hashlib.sha256(response.content).hexdigest() + '"'
    if request.headers.get('If-None-Match') == response['ETag']:
        response.status_code = 304
        response.content = b''
    return response


@require_GET
@cache_control(public=True, max_age=0, must_revalidate=True)
def detail(request, slug):
    return JsonResponse(cached_payload(request, lambda: serialize(get_object_or_404(public_products(), slug=slug))))


@require_GET
@cache_control(public=True, max_age=0, must_revalidate=True)
def categories(request):
    return JsonResponse({'categories':list(Category.objects.filter(is_active=True).annotate(
        product_count=Count('products', filter=Q(products__is_active=True, products__is_published=True, products__is_archived=False))
    ).values('id', 'name', 'slug', 'product_count')), 'subcategories':list(Subcategory.objects.filter(is_active=True, category__is_active=True).values('id','category_id','name','slug'))})


@require_GET
@cache_control(public=True, max_age=0, must_revalidate=True)
def homepage(request):
    def load():
        return {section:[serialize(product) for product in paginate({'section':section,'limit':12})[0]]
                for section in ('new_arrival','featured','best_seller','for_you')}
    return JsonResponse(cached_payload(request, load))


@require_POST
@never_cache
def checkout(request):
    if not request.user.is_authenticated:
        return JsonResponse({'errors':['Sign in to checkout.']}, status=401)
    try:
        payload = json.loads(request.body)
        if not isinstance(payload, dict):
            raise ValueError()
        order = reserve_order(request.user, payload.get('items'), request.headers.get('Idempotency-Key', ''))
    except (ValueError, TypeError, ValidationError) as exc:
        return JsonResponse({'errors':getattr(exc, 'messages', ['Invalid checkout request.'])}, status=400)
    return JsonResponse({'id':order.pk, 'total':str(order.total), 'status':order.status, 'payment_processed':False}, status=201)


@require_POST
@never_cache
def cart_quote(request):
    """Revalidate a browser basket without placing an order or taking payment."""
    try:
        data = json.loads(request.body)
        items = data.get('items') if isinstance(data, dict) else None
        if not isinstance(items, list) or not 1 <= len(items) <= 100:
            raise ValidationError('Your basket must contain between 1 and 100 products.')
        quantities = {}
        for item in items:
            if not isinstance(item, dict) or type(item.get('product_id')) is not int or type(item.get('quantity')) is not int or not 1 <= item['quantity'] <= 10000:
                raise ValidationError('Invalid basket item.')
            quantities[item['product_id']] = quantities.get(item['product_id'], 0) + item['quantity']
        products = list(public_products().filter(pk__in=quantities))
        if len(products) != len(quantities):
            raise ValidationError('A basket item is no longer available. Remove it before continuing.')
        lines, total = [], Decimal('0')
        for product in products:
            quantity = quantities[product.pk]
            if not product.available or quantity > product.stock:
                raise ValidationError(f'{product.name}: insufficient confirmed stock.')
            total += product.price * quantity
            lines.append(dict(**serialize(product), quantity=quantity))
        return JsonResponse({'items':lines, 'subtotal':str(total)})
    except (ValueError, TypeError, ValidationError) as exc:
        return JsonResponse({'errors':getattr(exc, 'messages', ['Invalid basket.'])}, status=400)
