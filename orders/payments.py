from datetime import timedelta
import stripe
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from catalog.models import Order
from .models import Payment, ProviderEvent, Refund
from .services import emit, finalize_cancel


def demo_enabled():
    return settings.DEBUG and settings.ORDER_PAYMENT_MODE == 'demo'


@transaction.atomic
def confirm_demo(order_id):
    if not demo_enabled():
        raise ValidationError('Local demo payments are disabled.')
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.payment_method != 'demo':
        raise ValidationError('This is not a demo order.')
    if order.payment_status == 'paid':
        return order
    if order.fulfilment_status != 'pending_payment' or order.cancellation_status != 'none' or order.reservation_expires_at <= timezone.now():
        raise ValidationError('This reservation is no longer payable.')
    payment = Payment.objects.select_for_update().get(order=order)
    payment.status = 'paid'
    payment.intent_id = 'demo_' + str(order.public_id)
    payment.save()
    order.payment_status = 'paid'
    order.fulfilment_status = 'placed'
    from .vouchers import consume
    consume(order)
    emit(order,'payment_confirmed','Demo payment confirmed. No money was charged.')
    return order


def client():
    key = settings.STRIPE_SECRET_KEY
    if not key.startswith(('sk_test_', 'rk_test_')):
        raise ValidationError('Stripe test payments are not configured.')
    return stripe.StripeClient(key, max_network_retries=2)


def create_session(order):
    if order.payment_method == 'voucher' and order.payment_status == 'paid':
        return f'/track-order/?order={order.public_id}'
    # Stripe idempotency serializes concurrent requests without holding a DB
    # transaction open during the remote call.
    if order.payment_method == 'demo':
        if not demo_enabled():
            raise ValidationError('Local demo payments are disabled.')
        return f'/payment/?order={order.public_id}&demo=1'
    gateway = client()
    payment = Payment.objects.get(order=order)
    if order.fulfilment_status != 'pending_payment' or order.cancellation_status != 'none':
        raise ValidationError('This order cannot start a payment.')
    if payment.session_url:
        return payment.session_url
    if order.reservation_expires_at <= timezone.now():
        raise ValidationError('The reservation has expired. Please create a new checkout.')
    origin = settings.ORDER_PUBLIC_ORIGIN
    session = gateway.v1.checkout.sessions.create(params={
        'mode':'payment','customer_email':order.email,
        'client_reference_id':str(order.public_id),
        'metadata':{'order_id':str(order.public_id)},
        'payment_intent_data':{'metadata':{'order_id':str(order.public_id)}},
        'line_items':[{'quantity':1,'price_data':{'currency':'gbp',
            'unit_amount':int(order.total*100),'product_data':{'name':f'Terai Foods {order.number} (including delivery)'}}}],
        'success_url':f'{origin}/track-order/?order={order.public_id}',
        'cancel_url':f'{origin}/track-order/?order={order.public_id}',
        # The reservation worker explicitly expires unpaid sessions after the
        # configured window. Omitting expires_at keeps retries' payload stable.
    }, options={'idempotency_key':f'checkout-{order.public_id}'})
    with transaction.atomic():
        locked = Order.objects.select_for_update().get(pk=order.pk)
        payment = Payment.objects.select_for_update().get(order=locked)
        payment.session_id,payment.session_url = session.id,session.url
        payment.save()
        cancelled = locked.fulfilment_status == 'cancelled' or locked.cancellation_status != 'none'
    if cancelled:
        gateway.v1.checkout.sessions.expire(session.id, options={'idempotency_key':f'expire-{order.public_id}'})
        raise ValidationError('This order has been cancelled.')
    return session.url


@transaction.atomic
def apply_event(event):
    """Only called after signature verification, never from browser success."""
    if hasattr(event, 'to_dict'):
        event = event.to_dict()
    event_id, kind = event['id'], event['type']
    if ProviderEvent.objects.filter(event_id=event_id).exists():
        return
    data = event['data']['object']
    if event.get('livemode'):
        raise ValidationError('Live payments are disabled for this integration.')
    order_id = data.get('metadata',{}).get('order_id')
    if kind.startswith('checkout.session.'):
        try:
            order = Order.objects.select_for_update().get(public_id=order_id)
        except (Order.DoesNotExist,ValueError):
            raise ValidationError('Unknown order reference.')
        payment = Payment.objects.select_for_update().get(order=order)
        if order.payment_method != 'stripe':
            raise ValidationError('Payment provider does not match this order.')
        if ProviderEvent.objects.filter(event_id=event_id).exists():
            return
        if payment.session_id and payment.session_id != data.get('id'):
            raise ValidationError('Payment session does not match the order.')
        if kind in ('checkout.session.completed','checkout.session.async_payment_succeeded') and data.get('payment_status') == 'paid':
            if data.get('currency') != 'gbp' or data.get('amount_total') != int(order.total*100):
                raise ValidationError('Payment amount or currency mismatch.')
            if order.payment_status not in ('paid','refunded'):
                payment.status,payment.session_id,payment.intent_id = 'paid',data['id'],data.get('payment_intent','')
                payment.save()
                order.payment_status = 'paid'
                if order.fulfilment_status == 'cancelled':
                    Refund.objects.get_or_create(order=order,defaults={'amount':order.total,'reason':'Payment received after cancellation'})
                    order.refund_status = 'pending'
                else:
                    order.fulfilment_status = 'placed'
                    from .vouchers import consume
                    consume(order)
                emit(order,'payment_confirmed','Payment confirmed.')
        elif kind == 'checkout.session.expired' and order.payment_status not in ('paid','refunded'):
            payment.status = 'expired'
            payment.save(update_fields=['status'])
            order.payment_status = 'expired'
            order.save(update_fields=['payment_status'])
            finalize_cancel(order.pk, reason='Payment reservation expired.')
        elif kind == 'checkout.session.async_payment_failed' and order.payment_status not in ('paid','refunded'):
            order.payment_status = 'failed'
            payment.status = 'failed'
            payment.save(update_fields=['status'])
            emit(order,'payment_failed','Payment failed. Please retry before the reservation expires.')
    elif kind in ('refund.updated','refund.created','refund.failed'):
        refund = Refund.objects.select_related('order').filter(provider_id=data.get('id')).first()
        if refund:
            order = Order.objects.select_for_update().get(pk=refund.order_id)
            refund = Refund.objects.select_for_update().get(pk=refund.pk)
            if data.get('amount') != int(refund.amount*100) or data.get('currency') != 'gbp':
                raise ValidationError('Refund amount mismatch.')
            state = data.get('status','pending')
            if refund.status != 'succeeded' and refund.status != state:
                refund.status = state
                refund.save(update_fields=['status'])
                order.refund_status = 'refunded' if state == 'succeeded' else state
                if state == 'succeeded':
                    order.payment_status = 'refunded'
                emit(order,'refund_'+state,'Refund '+state+'.')
    ProviderEvent.objects.get_or_create(event_id=event_id,defaults={'event_type':kind})


def cancel_with_provider(order_id, reason='Cancellation requested'):
    order = Order.objects.get(pk=order_id)
    payment = Payment.objects.get(order=order)
    if order.fulfilment_status == 'cancelled':
        return order
    if payment.session_id and order.payment_status != 'paid':
        gateway = client()
        session = gateway.v1.checkout.sessions.retrieve(payment.session_id)
        if session.status == 'open':
            try:
                gateway.v1.checkout.sessions.expire(payment.session_id, options={'idempotency_key':f'expire-{order.public_id}'})
            except stripe.InvalidRequestError:
                session = gateway.v1.checkout.sessions.retrieve(payment.session_id)
                if session.status == 'open':
                    raise
        if session.payment_status == 'paid':
            apply_event({'id':f'reconcile-{session.id}','type':'checkout.session.completed',
                         'livemode':False,'data':{'object':session.to_dict()}})
    return finalize_cancel(order_id,reason=reason)


def process_refund(refund_id):
    refund = Refund.objects.select_related('order__payment').get(pk=refund_id)
    if refund.status in ('succeeded','awaiting_manual'):
        return
    if refund.order.payment_method == 'demo':
        if not demo_enabled():
            raise ValidationError('Local demo refunds are disabled.')
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=refund.order_id)
            locked = Refund.objects.select_for_update().get(pk=refund.pk)
            if locked.status == 'succeeded':
                return
            locked.status, locked.provider_id = 'succeeded', 'demo_' + str(order.public_id)
            locked.save()
            order.payment_status, order.refund_status = 'refunded', 'refunded'
            emit(order,'refund_succeeded','Demo refund completed. No money was transferred.')
        return
    if not refund.order.payment.intent_id:
        raise ValidationError('A payment reference is required for this refund.')
    gateway = client()
    result = gateway.v1.refunds.retrieve(refund.provider_id) if refund.provider_id else gateway.v1.refunds.create(params={'payment_intent':refund.order.payment.intent_id,
        'amount':int(refund.amount*100),'metadata':{'order_id':str(refund.order.public_id)}},
        options={'idempotency_key':f'refund-{refund.order.public_id}'})
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=refund.order_id)
        locked = Refund.objects.select_for_update().get(pk=refund.pk)
        if locked.status == 'succeeded' or (locked.provider_id == result.id and locked.status == result.status):
            return
        locked.provider_id,locked.status = result.id,result.status
        locked.save()
        order.refund_status = 'refunded' if result.status == 'succeeded' else result.status
        if result.status == 'succeeded':
            order.payment_status = 'refunded'
        emit(order,'refund_'+result.status,'Refund '+result.status+'.')
