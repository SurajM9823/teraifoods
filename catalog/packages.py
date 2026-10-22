from collections import defaultdict
from django.core.exceptions import ValidationError
from .models import Product, PackageItem
from .services import require_public


def present(product):
    """Fill existing template fields on a read-only display instance."""
    if product and product.is_package:
        product.stock=product.effective_stock
        product.regular_price=product.base_price
        product.sale_price=product.price if product.price<product.regular_price else None
        contents='\n'.join(f'{line.quantity} x {line.product.name}' for line in product.package_config.components.select_related('product'))
        product.description=(product.description+'\n\nPackage contents:\n'+contents).strip()
    return product


def basket(products, quantities, *, locked=None):
    """Expand bundles and regular lines into a single physical inventory demand."""
    demand=defaultdict(int)
    snapshots={}
    for product in products:
        require_public(product)
        if product.is_package:
            components=list(product.package_config.components.select_related('product'))
            if not components:
                raise ValidationError('This package has no products.')
            snapshots[product.pk]=[]
            for line in components:
                if line.product.is_package:
                    raise ValidationError('Nested packages are not supported.')
                demand[line.product_id]+=line.quantity*quantities[product.pk]
                snapshots[product.pk].append({'product_id':line.product_id,'quantity':line.quantity,'name':line.product.name})
        else:
            demand[product.pk]+=quantities[product.pk]
    physical=locked or {p.pk:p for p in Product.objects.filter(pk__in=demand).select_related('category','subcategory')}
    for pk,quantity in demand.items():
        product=physical.get(pk)
        if not product:
            raise ValidationError('Package contents changed during checkout. Please retry.')
        require_public(product)
        if not product.stock_confirmed or product.stock<quantity:
            raise ValidationError(f'{product.name}: insufficient stock for the combined basket.')
    return demand,snapshots


def lock_basket(quantities):
    ids=set(quantities)
    ids.update(PackageItem.objects.filter(package__product_id__in=quantities).values_list('product_id',flat=True))
    locked={p.pk:p for p in Product.objects.select_for_update().filter(pk__in=ids).order_by('pk').prefetch_related('images')}
    if not set(quantities)<=locked.keys():
        raise ValidationError('A product no longer exists.')
    products=[locked[pk] for pk in quantities]
    demand,snapshots=basket(products,quantities,locked=locked)
    return products,demand,snapshots
