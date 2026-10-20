import logging
from datetime import timedelta
from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from catalog.models import Order
from .models import OrderEvent, Notification, Refund
from .services import guest_token

logger = logging.getLogger(__name__)


@shared_task(bind=True,max_retries=5)
def send_notification(self, pk):
    with transaction.atomic():
        notification = Notification.objects.select_for_update().select_related('event__order').get(pk=pk)
        if notification.status == 'sent':
            return
        if notification.status == 'sending' and notification.claimed_at and notification.claimed_at > timezone.now()-timedelta(minutes=5):
            return
        notification.status = 'sending'
        notification.claimed_at = timezone.now()
        notification.attempts += 1
        notification.save()
    order = notification.event.order
    url = f'{settings.ORDER_PUBLIC_ORIGIN}/track-order/?order={order.public_id}'
    if order.customer_id is None:
        url += '#access='+guest_token(order)
    body = f'{order.number}\n{notification.event.message}\n\nTrack your order: {url}\n'
    if notification.secret_payload:
        from customers.email_backend import mail_cipher
        body += '\nDelivery verification code: '+mail_cipher().decrypt(notification.secret_payload.encode()).decode()+'\nShare this code only at handover.'
    try:
        sent = EmailMessage(f'Terai Foods {order.number}: {notification.event.event_type.replace("_"," ")}',
            body,settings.DEFAULT_FROM_EMAIL,[notification.recipient],
            connection=get_connection(settings.EMAIL_DELIVERY_BACKEND),
            headers={'Message-ID':f'<order-event-{notification.event_id}@teraifoods.co.uk>'}).send()
        if sent != 1:
            raise RuntimeError('Delivery not accepted')
    except Exception:
        Notification.objects.filter(pk=pk).update(status='pending')
        raise self.retry(exc=RuntimeError('Order email delivery failed'),countdown=min(60*2**self.request.retries,1800))
    Notification.objects.filter(pk=pk).update(status='sent',sent_at=timezone.now(),secret_payload='')


@shared_task
def dispatch_pending():
    for event in OrderEvent.objects.filter(broadcast_at__isnull=True).select_related('order')[:200]:
        try:
            async_to_sync(get_channel_layer().group_send)(f'order.{event.order.public_id}',
                {'type':'order.changed','version':event.version})
        except Exception:
            logger.warning('Order event broadcast unavailable; will retry.')
            break
        else:
            OrderEvent.objects.filter(pk=event.pk).update(broadcast_at=timezone.now())
    for pk in Notification.objects.filter(Q(status='pending')|Q(status='sending',claimed_at__lt=timezone.now()-timedelta(minutes=5))).values_list('pk',flat=True)[:200]:
        send_notification.delay(pk)
    from .payments import cancel_with_provider,process_refund
    for order in Order.objects.filter(cancellation_status='requested')[:100]:
        try:
            cancel_with_provider(order.pk)
        except Exception:
            logger.warning('Cancellation reconciliation pending for order %s',order.pk)
    for refund in Refund.objects.filter(status='pending')[:100]:
        try:
            process_refund(refund.pk)
        except Exception:
            logger.warning('Refund reconciliation pending for order %s',refund.order_id)


@shared_task
def expire_reservations():
    from .payments import cancel_with_provider
    orders = Order.objects.filter(fulfilment_status='pending_payment',reservation_expires_at__lt=timezone.now()).exclude(payment_status='paid')
    for order in orders[:100]:
        try:
            cancel_with_provider(order.pk,'Payment reservation expired.')
        except Exception:
            logger.warning('Reservation reconciliation pending for order %s',order.pk)
