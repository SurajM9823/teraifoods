import hashlib
import json
import re
import secrets
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
from django.core import signing
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from catalog.models import Order, OrderLine, Product
from catalog.services import adjust_stock, require_public
from delivery.services import quote_delivery
from .models import CheckoutAttempt, Payment, OrderEvent, Notification, Refund, ReturnRequest, DeliveryAttempt

TRANSITIONS = {
    'placed':{'confirmed','cancelled'},
    'confirmed':{'preparing','cancelled'},
    'preparing':{'ready_for_dispatch'},
    'ready_for_dispatch':{'dispatched'},
    'dispatched':{'out_for_delivery','delivery_failed'},
    'out_for_delivery':{'delivery_failed'},
    'delivery_failed':{'out_for_delivery'},
}
CANCELLABLE = {'pending_payment','placed','confirmed'}


def update_rating(product_id):
    from django.db.models import Avg, Count
    from .models import Review
    values = Review.objects.filter(product_id=product_id,status='approved').aggregate(rating=Avg('rating'),count=Count('id'))
    product = Product.objects.get(pk=product_id)
    product.rating = values['rating']
    product.review_count = values['count']
    product.save(update_fields=['rating','review_count'])


def normalize_address(data):
    if not isinstance(data, dict):
        raise ValidationError('Enter a delivery address.')
    fields = {'name':150,'phone':30,'line1':200,'line2':200,'city':100,'county':100,'instructions':500}
    result = {}
    for name, limit in fields.items():
        value = data.get(name, '')
        if not isinstance(value, str) or len(value) > limit:
            raise ValidationError(f'Invalid address field: {name}.')
        result[name] = value.strip()
    for name in ('name','phone','line1','city'):
        if not result[name]:
            raise ValidationError(f'Enter {name}.')
    phone = re.sub(r'[\s().-]', '', result['phone'])
    if not re.fullmatch(r'(?:\+44|0044|0)\d{9,10}', phone):
        raise ValidationError('Enter a valid UK contact number.')
    postcode = re.sub(r'\s', '', str(data.get('postcode', '')).upper())
    if not re.fullmatch(r'(?:GIR0AA|[A-Z]{1,2}\d[A-Z\d]?\d[A-Z]{2})', postcode):
        raise ValidationError('Enter a valid UK postcode.')
    if postcode.startswith(('JE','GY','IM')) or data.get('country', 'GB') not in ('GB','UK'):
        raise ValidationError('Delivery coverage is the United Kingdom.')
    result.update(phone=phone, postcode=postcode[:-3]+' '+postcode[-3:], country='GB', verification='manual')
    return result


def guest_token(order):
    return signing.dumps({'order':str(order.public_id),'version':order.guest_access_version}, salt='guest-order-access', compress=True)


def authorize(order, user, session):
    if user.is_authenticated and (order.customer_id == user.pk or (user.is_staff and user.has_perm('catalog.view_order'))):
        return
    if str(order.public_id) in session.get('order_grants', {}):
        grant = session['order_grants'][str(order.public_id)]
        if grant.get('version') == order.guest_access_version and grant.get('expires', 0) > timezone.now().timestamp():
            return
    raise PermissionDenied('This order is not available to this session.')


def grant_access(session, order):
    grants = session.get('order_grants', {})
    grants[str(order.public_id)] = {'version':order.guest_access_version,
        'expires':(timezone.now()+timedelta(days=settings.ORDER_GUEST_ACCESS_DAYS)).timestamp()}
    session['order_grants'] = dict(list(grants.items())[-20:])


def redeem_token(session, token):
    try:
        data = signing.loads(token, salt='guest-order-access', max_age=settings.ORDER_GUEST_ACCESS_DAYS*86400)
        order = Order.objects.get(public_id=data['order'], guest_access_version=data['version'])
    except (signing.BadSignature, KeyError, ValueError, Order.DoesNotExist):
        raise PermissionDenied('Tracking link is invalid or expired.')
    grant_access(session, order)
    return order


def emit(order, event_type, message, actor=None, secret=''):
    # Call only while holding the order row lock. This durable outbox is retried
    # by Celery; no broker or SMTP call runs in the checkout transaction.
    order.version += 1
    order.save()
    event = OrderEvent.objects.create(order=order,version=order.version,event_type=event_type,message=message,actor=actor)
    if order.email:
        Notification.objects.create(event=event,recipient=order.email,secret_payload=secret)
    def schedule():
        from .tasks import dispatch_pending
        try:
            dispatch_pending.apply_async(retry=False)
        except Exception:
            # Beat retries this durable outbox if the broker is unavailable.
            import logging
            logging.getLogger(__name__).warning('Order outbox queued for periodic recovery.')
    transaction.on_commit(schedule)
    return event


@transaction.atomic
def create_order(user, scope, payload, key):
    if not isinstance(payload, dict) or not isinstance(key,str) or not 1 <= len(key) <= 100:
        raise ValidationError('A checkout idempotency key is required.')
    address = normalize_address(payload.get('address'))
    email = payload.get('email', '')
    if not isinstance(email,str):
        raise ValidationError('Enter an email address.')
    email = email.strip().lower()
    validate_email(email)
    if len(email) > 254:
        raise ValidationError('Email address is too long.')
    items = payload.get('items')
    if not isinstance(items,list) or not 1 <= len(items) <= 100:
        raise ValidationError('Choose between 1 and 100 basket items.')
    quantities = {}
    for item in items:
        if not isinstance(item,dict) or type(item.get('product_id')) is not int or type(item.get('quantity')) is not int or not 1 <= item['quantity'] <= 10000:
            raise ValidationError('Invalid basket item.')
        quantities[item['product_id']] = quantities.get(item['product_id'],0) + item['quantity']
    digest = hashlib.sha256(json.dumps({'items':sorted(quantities.items()),'address':address,'email':email},sort_keys=True).encode()).hexdigest()
    scoped_key = hashlib.sha256(f'{scope}:{key}'.encode()).hexdigest()
    attempt, _ = CheckoutAttempt.objects.get_or_create(key=scoped_key,defaults={'digest':digest})
    attempt = CheckoutAttempt.objects.select_for_update().get(pk=attempt.pk)
    if attempt.digest != digest:
        raise ValidationError('This checkout key was already used for a different basket or address.')
    if attempt.order_id:
        return attempt.order
    products = list(Product.objects.select_for_update().filter(pk__in=quantities).order_by('pk').prefetch_related('images'))
    if len(products) != len(quantities):
        raise ValidationError('A product no longer exists.')
    subtotal, discount = Decimal('0'), Decimal('0')
    for product in products:
        require_public(product)
        if not product.stock_confirmed or product.stock < quantities[product.pk]:
            raise ValidationError(f'{product.name}: insufficient stock.')
        subtotal += product.price * quantities[product.pk]
        discount += (product.regular_price-product.price) * quantities[product.pk]
    shipping = quote_delivery(products, quantities, lock=True)
    order = Order.objects.create(customer=user if user.is_authenticated else None, email=email,
        recipient_name=address['name'],phone=address['phone'],address=address,
        idempotency_key=scoped_key, request_digest=digest, subtotal=subtotal,discount=discount,
        delivery_charge=shipping['charge'],total=subtotal+shipping['charge'],total_weight_grams=shipping['weight_grams'],
        delivery_min_days=shipping['minimum_days'],delivery_max_days=shipping['maximum_days'],
        reservation_expires_at=timezone.now()+timedelta(minutes=settings.ORDER_RESERVATION_MINUTES))
    for product in products:
        quantity = quantities[product.pk]
        OrderLine.objects.create(order=order,product=product,quantity=quantity,unit_price=product.price,
            unit_weight_grams=product.weight_grams,product_name=product.name,product_image=product.image_url,product_sku=product.sku)
        adjust_stock(product.pk,-quantity,reason='Checkout reservation',actor=user if user.is_authenticated else None,
            key=f'order:{order.pk}:{product.pk}',kind='order',reference=order.number)
    Payment.objects.create(order=order,amount=order.total)
    attempt.order = order
    attempt.save(update_fields=['order'])
    emit(order,'placed','Order created; payment is pending.',user if user.is_authenticated else None)
    return order


def restore_stock(order, actor, kind='cancellation'):
    for line in order.lines.order_by('product_id'):
        adjust_stock(line.product_id,line.quantity,reason=f'Order {kind}',actor=actor,
            key=f'{kind}:{order.pk}:{line.product_id}',kind=kind,reference=order.number)


@transaction.atomic
def finalize_cancel(order_id, actor=None, reason='Cancellation requested'):
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.fulfilment_status == 'cancelled':
        return order
    if order.fulfilment_status not in CANCELLABLE:
        raise ValidationError('This order can no longer be cancelled before dispatch.')
    restore_stock(order,actor)
    order.fulfilment_status = 'cancelled'
    order.status = 'cancelled'
    order.cancellation_status = 'cancelled'
    if order.payment_status == 'paid':
        Refund.objects.get_or_create(order=order,defaults={'amount':order.total,'reason':reason})
        order.refund_status = 'pending'
    emit(order,'cancelled',reason,actor)
    return order


@transaction.atomic
def request_cancel(order_id, reason, actor=None):
    if not isinstance(reason,str) or not reason.strip() or len(reason)>500:
        raise ValidationError('Enter a cancellation reason.')
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.cancellation_status != 'none':
        return order
    if order.fulfilment_status not in CANCELLABLE:
        raise ValidationError('This order is already being prepared or dispatched. Contact support.')
    order.cancellation_status = 'requested'
    emit(order,'cancellation_requested',reason,actor)
    return order


@transaction.atomic
def transition(order_id, target, actor, reason=''):
    order = Order.objects.select_for_update().get(pk=order_id)
    if target == order.fulfilment_status:
        return order
    if target == 'cancelled':
        raise ValidationError('Use the cancellation workflow to release inventory and refund payments.')
    if order.payment_status != 'paid' or order.cancellation_status == 'requested':
        raise ValidationError('Confirm payment and resolve cancellation before fulfilment.')
    if target not in TRANSITIONS.get(order.fulfilment_status,set()):
        raise ValidationError('Invalid order status transition.')
    order.fulfilment_status = target
    emit(order,target,reason or target.replace('_',' ').capitalize(),actor)
    return order


@transaction.atomic
def request_return(order_id, reason, actor=None):
    order = Order.objects.select_for_update().get(pk=order_id)
    if hasattr(order,'return_request'):
        return order.return_request
    if not isinstance(reason,str) or not reason.strip() or len(reason)>1000:
        raise ValidationError('Enter a return reason.')
    if order.fulfilment_status != 'delivered' or not order.delivered_at:
        raise ValidationError('Returns can be requested after delivery.')
    # Zero means manual review, never an automatic promise of return eligibility.
    if settings.ORDER_RETURN_DAYS and timezone.now() > order.delivered_at + timedelta(days=settings.ORDER_RETURN_DAYS):
        raise ValidationError('The online return window has ended. Contact support.')
    result = ReturnRequest.objects.create(order=order,reason=reason)
    emit(order,'return_requested','Return requested.',actor)
    return result


@transaction.atomic
def decide_return(order_id, target, reason, actor, restock=False):
    order = Order.objects.select_for_update().get(pk=order_id)
    request = ReturnRequest.objects.select_for_update().filter(order=order).first()
    if request is None:
        raise ValidationError('No return has been requested for this order.')
    allowed = {'requested':{'approved','rejected'},'approved':{'received'}}
    if target == request.status:
        return request
    if target not in allowed.get(request.status,set()) or not reason:
        raise ValidationError('Select a valid return decision and record a reason.')
    request.status,request.admin_reason = target,reason
    request.save()
    if target == 'received':
        if restock:
            restore_stock(order,actor,kind='return')
        Refund.objects.get_or_create(order=order,defaults={'amount':order.total,'reason':reason})
        order.refund_status = 'pending'
    emit(order,'return_'+target,'Return '+target+'.',actor)
    return request


@transaction.atomic
def support_message(order_id, message, actor=None, reply=False):
    if not isinstance(message,str) or not message.strip() or len(message)>500:
        raise ValidationError('Enter a message of up to 500 characters.')
    order = Order.objects.select_for_update().get(pk=order_id)
    emit(order,'support_reply' if reply else 'support_requested',message.strip(),actor)
    return order


@transaction.atomic
def issue_delivery_pin(order_id, actor):
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.fulfilment_status not in ('dispatched','out_for_delivery','delivery_failed'):
        raise ValidationError('Delivery verification is available during an active delivery.')
    pin = f'{secrets.randbelow(1000000):06d}'
    order.delivery_pin_hash = make_password(pin)
    order.delivery_pin_attempts = 0
    order.delivery_pin_expires_at = timezone.now()+timedelta(hours=24)
    from customers.email_backend import mail_cipher
    encrypted = mail_cipher().encrypt(pin.encode()).decode()
    emit(order,'delivery_pin','Your delivery verification code is ready.',actor,secret=encrypted)
    # The PIN is delivered to the recipient only, never returned to the driver.


def complete_delivery(order_id, actor, *, pin='', alternative_reason=''):
    error = None
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        if order.assigned_driver_id != actor.pk and not actor.has_perm('catalog.change_order'):
            raise PermissionDenied
        if order.fulfilment_status == 'delivered':
            return order
        if order.fulfilment_status != 'out_for_delivery':
            raise ValidationError('The order must be out for delivery.')
        verified = (order.delivery_pin_attempts < 5 and order.delivery_pin_expires_at and
            order.delivery_pin_expires_at > timezone.now() and check_password(str(pin),order.delivery_pin_hash))
        alternative = bool(alternative_reason and actor.has_perm('catalog.change_order') and not settings.ORDER_DELIVERY_PIN_REQUIRED)
        success = bool(verified or alternative)
        order.delivery_pin_attempts = min(order.delivery_pin_attempts + 1, 5)
        order.save(update_fields=['delivery_pin_attempts'])
        DeliveryAttempt.objects.create(order=order,actor=actor,method='pin' if verified else 'authorized_alternative',
            successful=success,reason=alternative_reason[:500] if alternative else '')
        if not success:
            error = 'Invalid, expired or locked delivery code.'
        else:
            order.fulfilment_status = 'delivered'
            order.delivered_at = timezone.now()
            order.delivery_pin_hash = ''
            emit(order,'delivered','Delivery confirmed.',actor)
    if error:
        raise ValidationError(error)
    return order
