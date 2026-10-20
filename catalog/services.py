"""All stock and image mutations serialize on the parent product row."""
import hashlib
import json
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import Product, ProductImage, StockAudit, Order, OrderLine


def require_public(product):
    if not (product.is_active and product.is_published and not product.is_archived
            and product.category_id and product.category.is_active
            and (not product.subcategory_id or product.subcategory.is_active)):
        raise ValidationError('This product is not available.')


@transaction.atomic
def adjust_stock(product_id, quantity, *, reason, actor, key, kind='correction', reference=''):
    if (type(quantity) is not int or not -2147483647 <= quantity <= 2147483647
            or not isinstance(key, str) or not key or len(key) > 100
            or not isinstance(reason, str) or not reason.strip() or len(reason) > 500
            or not isinstance(reference, str) or len(reference) > 100):
        raise ValidationError('Supply an integer quantity, reason and idempotency key.')
    if kind not in dict(StockAudit._meta.get_field('adjustment_type').choices):
        raise ValidationError('Invalid adjustment type.')
    product = Product.objects.select_for_update().get(pk=product_id)
    previous = StockAudit.objects.filter(idempotency_key=key).first()
    if previous:
        if (previous.product_id, previous.adjustment, previous.actor_id, previous.adjustment_type, previous.reason, previous.reference) != (product_id, quantity, getattr(actor, 'pk', None), kind, reason, reference):
            raise ValidationError('This idempotency key was already used for a different adjustment.')
        return previous
    if not 0 <= product.stock + quantity <= 2147483647:
        raise ValidationError('Insufficient stock. Stock cannot become negative.')
    if kind == 'initial' and product.stock_confirmed:
        raise ValidationError('Initial stock has already been recorded.')
    audit = StockAudit.objects.create(
        product=product, previous_quantity=product.stock, adjustment=quantity,
        new_quantity=product.stock + quantity, reason=reason, actor=actor,
        adjustment_type=kind, reference=reference, idempotency_key=key,
    )
    product.stock = audit.new_quantity
    product.stock_confirmed = True
    product.save(update_fields=['stock', 'stock_confirmed', 'updated_at'])
    return audit


@transaction.atomic
def set_main_image(product_id, image_id):
    product = Product.objects.select_for_update().get(pk=product_id)
    image = product.images.get(pk=image_id)
    product.images.filter(is_main=True).update(is_main=False)
    image.is_main = True
    image.save(update_fields=['is_main'])


@transaction.atomic
def delete_image(product_id, image_id, replacement_id=None):
    product = Product.objects.select_for_update().get(pk=product_id)
    image = product.images.get(pk=image_id)
    if image.is_main and product.is_published:
        if not replacement_id or str(replacement_id) == str(image_id):
            raise ValidationError('Select a replacement main image before deleting this image.')
        set_main_image(product_id, replacement_id)
    image.delete()
    # Content-addressed files are retained: other products may share them.


@transaction.atomic
def reorder_images(product_id, image_ids):
    product = Product.objects.select_for_update().get(pk=product_id)
    if len(image_ids) != len(set(image_ids)) or set(image_ids) != set(product.images.values_list('pk', flat=True)):
        raise ValidationError('Provide each existing image exactly once.')
    for position, image_id in enumerate(image_ids):
        image = product.images.get(pk=image_id)
        image.position = position
        image.save(update_fields=['position'])


def validate_publication(product):
    product.full_clean()
    if product.is_published and product.images.filter(is_main=True).count() != 1:
        raise ValidationError('A published product must have one main image.')


@transaction.atomic
def reserve_order(customer, items, key):
    if not key or len(key) > 100 or not isinstance(items, list) or not 1 <= len(items) <= 100:
        raise ValidationError('Supply a checkout key and between 1 and 100 items.')
    quantities = {}
    for item in items:
        if not isinstance(item, dict) or type(item.get('product_id')) is not int or type(item.get('quantity')) is not int or not 1 <= item['quantity'] <= 10000:
            raise ValidationError('Invalid product or quantity.')
        quantities[item['product_id']] = quantities.get(item['product_id'], 0) + item['quantity']
    digest = hashlib.sha256(json.dumps(sorted(quantities.items())).encode()).hexdigest()
    # Serialize this customer's duplicate submissions before creating the order.
    type(customer).objects.select_for_update().get(pk=customer.pk)
    existing = Order.objects.filter(idempotency_key=key).first()
    if existing:
        if existing.customer_id != customer.pk or existing.request_digest != digest:
            raise ValidationError('Checkout key has already been used.')
        return existing
    products = list(Product.objects.select_for_update().filter(pk__in=quantities).order_by('pk'))
    if len(products) != len(quantities):
        raise ValidationError('A product no longer exists.')
    total = Decimal('0')
    for product in products:
        require_public(product)
        if not product.stock_confirmed or product.stock < quantities[product.pk]:
            raise ValidationError(f'{product.name}: insufficient confirmed stock.')
        total += product.price * quantities[product.pk]
    order = Order.objects.create(customer=customer, idempotency_key=key, request_digest=digest, total=total)
    for product in products:
        OrderLine.objects.create(order=order, product=product, quantity=quantities[product.pk], unit_price=product.price)
        adjust_stock(product.pk, -quantities[product.pk], reason='Order reservation', actor=customer,
                     key=f'order:{order.pk}:{product.pk}', kind='order', reference=str(order.pk))
    return order


@transaction.atomic
def cancel_order(order_id, actor):
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.status == 'cancelled':
        return order
    for line in order.lines.order_by('product_id'):
        adjust_stock(line.product_id, line.quantity, reason='Order cancellation', actor=actor,
                     key=f'cancel:{order.pk}:{line.product_id}', kind='cancellation', reference=str(order.pk))
    order.status = 'cancelled'
    order.save(update_fields=['status'])
    return order
