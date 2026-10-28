from decimal import Decimal
import stripe
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from catalog.models import Order
from .models import Payment, ProviderEvent, Refund
from .services import emit, finalize_cancel
from .stripe_config import mode, validate, validate_payment


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
    validate()
    return stripe.StripeClient(settings.STRIPE_SECRET_KEY, max_network_retries=2)


def create_session(order, embedded=False):
    if order.payment_method == 'voucher' and order.payment_status == 'paid':
        return f'/track-order/?order={order.public_id}'
    # Stripe idempotency serializes concurrent requests without holding a DB
    # transaction open during the remote call.
    if order.payment_method == 'demo':
        if not demo_enabled():
            raise ValidationError('Local demo payments are disabled.')
        return f'/payment/?order={order.public_id}&demo=1'
    gateway = client()
    if embedded:
        validate_elements_config()
    payment = Payment.objects.get(order=order)
    validate_payment(payment)
    if order.fulfilment_status != 'pending_payment' or order.cancellation_status != 'none':
        raise ValidationError('This order cannot start a payment.')
    if order.reservation_expires_at <= timezone.now():
        raise ValidationError('The reservation has expired. Please create a new checkout.')
    origin = settings.ORDER_PUBLIC_ORIGIN
    params = {
        'mode':'payment','customer_email':order.email,
        'adaptive_pricing': {'enabled': False},
        'client_reference_id':str(order.public_id),
        'metadata':{'order_id':str(order.public_id)},
        'payment_intent_data':{'metadata':{'order_id':str(order.public_id)}},
        'line_items':[{'quantity':1,'price_data':{'currency':'gbp',
            'unit_amount':int(order.total*100),'product_data':{'name':f'Terai Foods {order.number} (including delivery)'}}}],
        'success_url':f'{origin}/track-order/?order={order.public_id}',
        'cancel_url':f'{origin}/track-order/?order={order.public_id}',
        # The reservation worker explicitly expires unpaid sessions after the
        # configured window. Omitting expires_at keeps retries' payload stable.
    }
    if embedded:
        params.pop('success_url')
        params.pop('cancel_url')
        params.update(ui_mode='elements', return_url=f'{origin}/track-order/?order={order.public_id}')
    if payment.session_id:
        session = gateway.v1.checkout.sessions.retrieve(payment.session_id)
    else:
        session = gateway.v1.checkout.sessions.create(params=params,
            options={'idempotency_key':f'checkout-{order.public_id}'})
    if (session.livemode is not (mode() == 'live') or session.currency != 'gbp'
            or session.amount_total != int(payment.amount * 100)
            or payment.amount != order.total or session.metadata['order_id'] != str(order.public_id)):
        raise ValidationError('Payment session does not match the order or Stripe mode.')
    with transaction.atomic():
        locked = Order.objects.select_for_update().get(pk=order.pk)
        payment = Payment.objects.select_for_update().get(order=locked)
        payment.session_id,payment.session_url = session.id,session.url or ''
        payment.save()
        cancelled = locked.fulfilment_status == 'cancelled' or locked.cancellation_status != 'none' or locked.reservation_expires_at <= timezone.now()
    if cancelled:
        gateway.v1.checkout.sessions.expire(session.id, options={'idempotency_key':f'expire-{order.public_id}'})
        raise ValidationError('This order has been cancelled.')
    if embedded:
        if session.status != 'open':
            raise ValidationError('This payment is complete or expired. Check your order status before retrying.')
        if session.url:
            # A previously created hosted Session must finish through its original flow.
            return {'payment_url': session.url, 'test_mode': mode() == 'test'}
        return {'client_secret': session.client_secret, 'publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
                'order_id': str(order.public_id), 'test_mode': mode() == 'test'}
    return session.url


def validate_elements_config():
    validate()


def payment_data(order):
    if order.payment_status in ('paid', 'refunded'):
        return {'payment_url': f'/track-order/?order={order.public_id}', 'test_mode': order.payment.stripe_mode == 'test'}
    result = create_session(order, embedded=order.payment_method == 'stripe')
    return result if isinstance(result, dict) else {'payment_url': result, 'test_mode': order.payment.stripe_mode == 'test'}


def reconcile(order):
    payment = Payment.objects.get(order=order)
    if order.payment_method == 'stripe' and payment.session_id and order.payment_status not in ('paid', 'refunded'):
        validate_payment(payment)
        session = client().v1.checkout.sessions.retrieve(payment.session_id)
        data = session.to_dict()
        if data.get('metadata', {}).get('order_id') != str(order.public_id):
            raise ValidationError('Payment reference does not match this order.')
        if session.payment_status == 'paid':
            apply_event({'id': f'reconcile-{session.id}', 'type': 'checkout.session.completed',
                         'livemode': session.livemode, 'data': {'object': data}})
        elif session.status == 'expired':
            apply_event({'id': f'expired-{session.id}', 'type': 'checkout.session.expired',
                         'livemode': session.livemode, 'data': {'object': data}})
    order.refresh_from_db()
    return order


@transaction.atomic
def apply_event(event):
    """Only called after signature verification, never from browser success."""
    if hasattr(event, 'to_dict'):
        event = event.to_dict()
    event_id, kind = event['id'], event['type']
    data = event['data']['object']
    if event.get('livemode') is not (mode() == 'live'):
        raise ValidationError('Webhook Stripe mode does not match the configured mode.')
    if 'livemode' in data and data['livemode'] is not event['livemode']:
        raise ValidationError('Webhook object Stripe mode mismatch.')
    if ProviderEvent.objects.filter(event_id=event_id).exists():
        return
    order_id = data.get('metadata',{}).get('order_id')
    if kind.startswith('checkout.session.'):
        try:
            order = Order.objects.select_for_update().get(public_id=order_id)
        except (Order.DoesNotExist,ValueError):
            raise ValidationError('Unknown order reference.')
        payment = Payment.objects.select_for_update().get(order=order)
        validate_payment(payment)
        if order.payment_method != 'stripe':
            raise ValidationError('Payment provider does not match this order.')
        if ProviderEvent.objects.filter(event_id=event_id).exists():
            return
        if payment.session_id and payment.session_id != data.get('id'):
            raise ValidationError('Payment session does not match the order.')
        if kind in ('checkout.session.completed','checkout.session.async_payment_succeeded') and data.get('payment_status') == 'paid':
            if (data.get('currency') != 'gbp' or data.get('amount_total') != int(payment.amount*100)
                    or payment.amount != order.total or not data.get('payment_intent')
                    or not data.get('id')):
                raise ValidationError('Payment amount or currency mismatch.')
            if payment.intent_id and payment.intent_id != data['payment_intent']:
                raise ValidationError('Payment intent does not match this order.')
            if order.payment_status not in ('paid','refunded'):
                payment.status,payment.session_id,payment.intent_id = 'paid',data['id'],data.get('payment_intent','')
                payment.save()
                order.payment_status = 'paid'
                if order.fulfilment_status == 'cancelled':
                    Refund.objects.get_or_create(order=order,defaults={'amount':order.total,'reason':'Payment received after cancellation'})
                    order.refund_status = 'pending'
                elif order.fulfilment_status == 'pending_payment':
                    order.fulfilment_status = 'placed'
                    from .vouchers import consume
                    consume(order)
                emit(order,'payment_confirmed','Payment confirmed.')
        elif kind == 'checkout.session.expired' and order.payment_status not in ('paid','refunded','expired'):
            payment.status = 'expired'
            payment.save(update_fields=['status'])
            order.payment_status = 'expired'
            order.save(update_fields=['payment_status'])
            finalize_cancel(order.pk, reason='Payment reservation expired.')
        elif kind == 'checkout.session.async_payment_failed' and order.payment_status not in ('paid','refunded','expired','failed'):
            order.payment_status = 'failed'
            payment.status = 'failed'
            payment.save(update_fields=['status'])
            emit(order,'payment_failed','Payment failed. Please retry before the reservation expires.')
    elif kind in ('refund.updated','refund.created','refund.failed'):
        refund = Refund.objects.select_related('order').filter(provider_id=data.get('id')).first()
        # A webhook may arrive before the API response has saved provider_id.
        if not refund and order_id:
            refund = Refund.objects.filter(order__public_id=order_id, provider_id='').first()
        if not refund:
            # Dashboard-initiated refunds can be matched by their paid intent.
            payment = Payment.objects.filter(intent_id=data.get('payment_intent'), stripe_mode=mode()).exclude(intent_id='').first()
            if payment:
                order = Order.objects.select_for_update().get(pk=payment.order_id)
                refund = Refund.objects.filter(order=order).first()
                if not refund:
                    if type(data.get('amount')) is not int or data['amount'] <= 0:
                        raise ValidationError('Invalid refund amount.')
                    refund = Refund.objects.create(order=order, amount=Decimal(data['amount']) / 100,
                                                   reason='Stripe Dashboard refund')
        if not refund:
            # Payment confirmation may arrive later. Allow Stripe to retry.
            raise ValidationError('Refund payment reference is not available yet.')
        apply_refund(refund.pk, data, failed=kind == 'refund.failed')
    ProviderEvent.objects.get_or_create(event_id=event_id,defaults={'event_type':kind})


def cancel_with_provider(order_id, reason='Cancellation requested', unpaid_only=False):
    order = Order.objects.get(pk=order_id)
    payment = Payment.objects.get(order=order)
    if order.payment_method == 'stripe':
        validate_payment(payment)
    if order.fulfilment_status == 'cancelled':
        return order
    if payment.session_id and order.payment_status not in ('paid', 'refunded'):
        gateway = client()
        session = gateway.v1.checkout.sessions.retrieve(payment.session_id)
        if session.livemode is not (mode() == 'live') or session.metadata['order_id'] != str(order.public_id):
            raise ValidationError('Payment session does not match this order or Stripe mode.')
        if session.status == 'open':
            try:
                gateway.v1.checkout.sessions.expire(payment.session_id, options={'idempotency_key':f'expire-{order.public_id}'})
            except stripe.InvalidRequestError:
                session = gateway.v1.checkout.sessions.retrieve(payment.session_id)
                if session.status == 'open':
                    raise
        if session.status == 'complete' and session.payment_status == 'unpaid' and order.payment_status != 'failed':
            raise ValidationError('Payment is still processing. Wait for provider confirmation before cancelling.')
        if session.payment_status == 'paid':
            apply_event({'id':f'reconcile-{session.id}','type':'checkout.session.completed',
                         'livemode':session.livemode,'data':{'object':session.to_dict()}})
    order.refresh_from_db()
    if unpaid_only and order.payment_status in ('paid', 'refunded'):
        raise ValidationError('This order has already been paid. Check your order before creating another payment.')
    return finalize_cancel(order_id,reason=reason)


def process_refund(refund_id):
    refund = Refund.objects.select_related('order__payment').get(pk=refund_id)
    if refund.status in ('succeeded','awaiting_manual','failed','canceled'):
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
    validate_payment(refund.order.payment)
    if (refund.order.payment.status != 'paid' or refund.amount <= 0
            or refund.amount > refund.order.payment.amount):
        raise ValidationError('Refund must not exceed the paid amount.')
    gateway = client()
    result = gateway.v1.refunds.retrieve(refund.provider_id) if refund.provider_id else gateway.v1.refunds.create(params={'payment_intent':refund.order.payment.intent_id,
        'amount':int(refund.amount*100),'metadata':{'order_id':str(refund.order.public_id), 'refund_id':str(refund.pk)}},
        options={'idempotency_key':f'refund-{refund.order.public_id}'})
    apply_refund(refund.pk, result.to_dict())


@transaction.atomic
def apply_refund(refund_id, data, failed=False):
    reference = Refund.objects.get(pk=refund_id)
    order = Order.objects.select_for_update().get(pk=reference.order_id)
    payment = Payment.objects.select_for_update().get(order=order)
    refund = Refund.objects.select_for_update().get(pk=refund_id)
    validate_payment(payment)
    if (order.payment_method != 'stripe' or not payment.intent_id
            or data.get('payment_intent') != payment.intent_id
            or data.get('currency') != 'gbp' or data.get('amount') != int(refund.amount * 100)
            or refund.amount <= 0 or refund.amount > payment.amount
            or not data.get('id') or (refund.provider_id and refund.provider_id != data['id'])
            or ('livemode' in data and data['livemode'] is not (mode() == 'live'))):
        raise ValidationError('Refund does not match the payment, amount or currency.')
    state = 'failed' if failed else data.get('status')
    if state not in ('pending', 'requires_action', 'succeeded', 'failed', 'canceled'):
        raise ValidationError('Unknown refund status.')
    # A bank can return a refund after it was initially reported successful.
    # Never let a stale pending/success snapshot erase a reported failure.
    if (refund.status in ('failed', 'canceled', 'awaiting_manual')
            or (refund.status == 'succeeded' and state not in ('failed', 'canceled'))):
        return
    changed = refund.status != state or refund.provider_id != data['id']
    refund.provider_id, refund.status = data['id'], state
    refund.save(update_fields=['provider_id', 'status'])
    if not changed:
        return
    order.refund_status = state
    if state in ('failed', 'canceled') and order.payment_status == 'refunded':
        order.payment_status = 'paid'
        payment.status = 'paid'
        payment.save(update_fields=['status'])
    if state == 'succeeded':
        full = refund.amount == payment.amount
        order.refund_status = 'refunded' if full else 'partially_refunded'
        if full:
            order.payment_status = 'refunded'
            payment.status = 'refunded'
            payment.save(update_fields=['status'])
    emit(order, 'refund_' + state, 'Refund ' + state + '.')
