from collections import defaultdict
from decimal import Decimal
from django.core.exceptions import ValidationError
from .models import Product, PackageItem
from .services import require_public


def present(product):
    """Fill existing template fields on a read-only display instance."""
    if product and product.is_package:
        product.stock = product.effective_stock
        product.regular_price = product.base_price
        product.sale_price = product.price if product.price < product.regular_price else None

        lines = product.package_lines
        for line in lines:
            line.unit_price = line.product.price
            line.line_total = (line.quantity * line.product.price).quantize(Decimal('.01')) if line.product.price else Decimal('0.00')
            if line.product.weight:
                line.unit_weight_display = f"{line.product.weight} {line.product.get_weight_unit_display()}"
            else:
                line.unit_weight_display = ""

        product.bundle_lines = lines
        product.bundle_items_count = sum(line.quantity for line in lines)
        product.bundle_products_count = len(lines)
        product.bundle_savings = max(Decimal('0.00'), (product.base_price - product.price)).quantize(Decimal('.01'))

        contents = ', '.join(f"{line.quantity}x {line.product.name}" for line in lines)
        pkg_config = getattr(product, 'package_config', None)
        tagline = f"{pkg_config.tagline}. " if pkg_config and pkg_config.tagline else ""
        if not product.description or 'Package contents:' in product.description:
            product.description = f"{tagline}Special curated grocery bundle containing {product.bundle_items_count} items ({contents}). Handpicked for authentic freshness and exceptional savings."
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
