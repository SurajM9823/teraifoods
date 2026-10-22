import json
import uuid
from datetime import timedelta
import stripe
from functools import wraps
from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.db.models import Avg, Count
from django.forms.models import model_to_dict
from django.core.paginator import Paginator
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from catalog.models import Order, OrderLine, Product
from catalog.media import prepare_image
from .models import Address, Review, ReviewImage, Notification
from . import services, payments


def api(view):
    @wraps(view)
    @never_cache
    def wrapped(request,*args,**kwargs):
        try:
            return view(request,*args,**kwargs)
        except PermissionDenied:
            return JsonResponse({'errors':['You do not have access to this order or action.']},status=403)
        except Http404:
            return JsonResponse({'errors':['Not found.']},status=404)
        except ValidationError as exc:
            return JsonResponse({'errors':exc.messages},status=400)
        except (ValueError,TypeError,KeyError):
            return JsonResponse({'errors':['Invalid request.']},status=400)
        except stripe.StripeError:
            response = JsonResponse({'errors':['Payment provider temporarily unavailable. Retry with the same checkout key.']},status=503)
            # Django skips session persistence on 5xx responses. Preserve the guest
            # checkout scope/grant so a provider outage cannot create another order.
            if request.session.modified:
                request.session.save()
                response.set_cookie(settings.SESSION_COOKIE_NAME, request.session.session_key,
                    max_age=request.session.get_expiry_age(), path=settings.SESSION_COOKIE_PATH,
                    domain=settings.SESSION_COOKIE_DOMAIN, secure=settings.SESSION_COOKIE_SECURE,
                    httponly=settings.SESSION_COOKIE_HTTPONLY, samesite=settings.SESSION_COOKIE_SAMESITE)
            return response
    return wrapped


def payload(request):
    data = json.loads(request.body)
    if not isinstance(data,dict):
        raise ValidationError('Expected a JSON object.')
    return data


def owned_order(request, public_id):
    order = get_object_or_404(Order.objects.prefetch_related('lines'),public_id=public_id)
    services.authorize(order,request.user,request.session)
    return order


def staff(request, permission='catalog.change_order'):
    if not request.user.is_authenticated or not request.user.is_active or not request.user.is_staff or not request.user.has_perm(permission):
        raise PermissionDenied


def order_data(order):
    stage = order.fulfilment_status
    group = 'completed' if stage=='delivered' else 'cancelled' if stage=='cancelled' else 'in-transit' if stage in ('dispatched','out_for_delivery','delivery_failed') else 'processing'
    return dict(id=str(order.public_id),number=order.number,version=order.version,
        created_at=order.created_at.isoformat(),payment_status=order.payment_status,payment_method=order.payment_method,fulfilment_status=stage,
        cancellation_status=order.cancellation_status,refund_status=order.refund_status,group=group,
        voucher_applied=str(services.vouchers.applied(order)),
        issued_voucher=(dict(code=order.issued_voucher.code,amount=str(order.issued_voucher.amount),used=bool(order.issued_voucher.redeemed_at)) if hasattr(order,'issued_voucher') else None),
        return_request=(dict(status=order.return_request.status,preference=order.return_request.refund_preference,
            method=order.return_request.settlement_method,reference=order.return_request.settlement_reference,
            note=order.return_request.admin_reason,amount=str(order.total)) if hasattr(order,'return_request') else None),
        subtotal=str(order.subtotal) if order.subtotal is not None else None,
        delivery_charge=str(order.delivery_charge) if order.delivery_charge is not None else None,total=str(order.total),
        currency=order.currency,address=order.address,
        delivery_estimate=f'{order.delivery_min_days}–{order.delivery_max_days} days' if order.delivery_min_days else None,
        tracking_reference=order.tracking_reference,tracking_url=order.tracking_url,
        can_cancel=stage in services.CANCELLABLE and order.cancellation_status=='none',
        can_return=stage=='delivered' and not hasattr(order,'return_request') and (
            not settings.ORDER_RETURN_DAYS or (order.delivered_at and timezone.now() <= order.delivered_at + timedelta(days=settings.ORDER_RETURN_DAYS))),
        items=[dict(id=line.pk,product_id=line.product_id,name=line.product_name or line.product.name,
            image=line.product_image,quantity=line.quantity,unit_price=str(line.unit_price),
            can_review=stage=='delivered' and not hasattr(line,'review')) for line in order.lines.select_related('product')],
        events=[{**event,'created_at':event['created_at'].isoformat()}
                for event in order.events.values('version','event_type','message','created_at')])


@api
@require_POST
def checkout(request):
    # A fully voucher-funded checkout does not need Stripe.
    if not request.session.get('checkout_scope'):
        request.session['checkout_scope'] = uuid.uuid4().hex
    scope = f'user:{request.user.pk}' if request.user.is_authenticated else 'guest:'+request.session['checkout_scope']
    with transaction.atomic():
        order = services.create_order(request.user,scope,payload(request),request.headers.get('Idempotency-Key',''))
        if order.total and order.payment_method=='stripe':
            payments.client()
            payments.validate_elements_config()
    services.grant_access(request.session,order)
    payment = payments.payment_data(order)
    return JsonResponse({'order':order_data(order), **payment},status=201)


@api
@require_POST
def payment_details(request, public_id):
    order = owned_order(request, public_id)
    return JsonResponse({'order': order_data(order), **payments.payment_data(order)})


@api
@require_POST
def payment_status(request, public_id):
    return JsonResponse(order_data(payments.reconcile(owned_order(request, public_id))))


@api
@require_POST
def access(request):
    order = services.redeem_token(request.session,payload(request).get('token',''))
    return JsonResponse(order_data(order))


@api
@require_GET
def detail(request, public_id):
    return JsonResponse(order_data(owned_order(request,public_id)))


@api
@require_GET
def history(request):
    if not request.user.is_authenticated:
        grants = list(request.session.get('order_grants',{}))
        queryset = Order.objects.filter(public_id__in=grants)
    else:
        queryset = Order.objects.filter(customer=request.user)
    result = []
    page = Paginator(queryset.order_by('-created_at'),20).get_page(request.GET.get('page'))
    for order in page:
        try:
            services.authorize(order,request.user,request.session)
        except PermissionDenied:
            continue
        result.append(order_data(order))
    return JsonResponse({'orders':result,'has_more':page.has_next(),
                         'next_page':page.next_page_number() if page.has_next() else None})


@api
@require_POST
def action(request, public_id):
    order = owned_order(request,public_id)
    data = payload(request)
    actor = request.user if request.user.is_authenticated else None
    if data.get('action')=='cancel':
        services.request_cancel(order.pk,data.get('reason',''),actor)
    elif data.get('action')=='return':
        services.request_return(order.pk,data.get('reason',''),actor,
            refund_preference=data.get('refund_preference','original'),bank_details=data.get('bank_details'))
    elif data.get('action')=='replace_payment':
        if order.fulfilment_status == 'cancelled' and order.payment_status not in ('paid', 'refunded'):
            return JsonResponse(order_data(order))
        if order.fulfilment_status != 'pending_payment' or order.payment_status in ('paid', 'refunded'):
            raise ValidationError('Check your existing order before starting another payment.')
        payments.cancel_with_provider(order.pk, reason='Checkout details changed.', unpaid_only=True)
    elif data.get('action')=='payment':
        return JsonResponse({'payment_url':f'/payment/?order={order.public_id}', 'test_mode':True})
    elif data.get('action')=='support':
        services.support_message(order.pk,data.get('reason',''),actor)
    elif data.get('action')=='demo_payment':
        payments.confirm_demo(order.pk)
    else:
        raise ValidationError('Choose cancellation, return or payment.')
    order.refresh_from_db()
    return JsonResponse(order_data(order))


@csrf_exempt
@api
@require_POST
def webhook(request):
    if not settings.STRIPE_WEBHOOK_SECRET:
        return JsonResponse({'errors':['Webhook not configured.']},status=503)
    try:
        event = stripe.Webhook.construct_event(request.body,request.headers.get('Stripe-Signature',''),
            settings.STRIPE_WEBHOOK_SECRET,tolerance=300)
    except (ValueError,stripe.SignatureVerificationError):
        return JsonResponse({'errors':['Invalid webhook signature.']},status=400)
    payments.apply_event(event)
    return JsonResponse({'received':True})


@api
@require_http_methods(['GET','POST','PATCH','DELETE'])
def addresses(request, pk=None):
    if not request.user.is_authenticated:
        raise PermissionDenied
    if request.method=='GET':
        return JsonResponse({'addresses':list(Address.objects.filter(customer=request.user).values()), 'customer_id':request.user.pk, 'email':request.user.email})
    with transaction.atomic():
        from django.contrib.auth import get_user_model
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        if request.method == 'PATCH' and not pk:
            raise ValidationError('Select an address to edit.')
        instance = get_object_or_404(Address,pk=pk,customer=request.user) if pk else Address(customer=request.user)
        if request.method=='DELETE':
            if not pk:
                raise ValidationError('Select an address.')
            instance.delete()
            return JsonResponse({'ok':True})
        data = payload(request)
        normalized = services.normalize_address(data)
        if not pk:
            existing = Address.objects.filter(customer=request.user, **normalized).first()
            if existing:
                instance = existing
        for key,value in normalized.items():
            setattr(instance,key,value)
        instance.is_default = data.get('is_default') is True
        if instance.is_default:
            Address.objects.filter(customer=request.user,is_default=True).update(is_default=False)
        instance.full_clean()
        instance.save()
    return JsonResponse({'address':model_to_dict(instance)},status=200 if pk else 201)


@api
@require_http_methods(['GET','POST'])
def reviews(request, product_id):
    from catalog.api import public_products
    product = get_object_or_404(public_products(),pk=product_id)
    if request.method=='GET':
        queryset = product.reviews.filter(status='approved')
        summary = queryset.aggregate(average=Avg('rating'),count=Count('id'))
        histogram = {row['rating']:row['count'] for row in queryset.values('rating').annotate(count=Count('id'))}
        return JsonResponse({'summary':summary,'histogram':histogram,'reviews':[dict(id=r.pk,rating=r.rating,title=r.title,
            text=r.text,name=r.display_name,date=r.created_at,verified=True,
            images=[image.url for image in r.images.all()]) for r in queryset.prefetch_related('images').order_by('-created_at')[:100]]})
    data = request.POST if request.content_type=='multipart/form-data' else payload(request)
    line = get_object_or_404(OrderLine.objects.select_related('order'),pk=data.get('order_line'),product=product)
    services.authorize(line.order,request.user,request.session)
    if line.order.fulfilment_status!='delivered':
        raise ValidationError('Reviews are available after delivery.')
    uploads = request.FILES.getlist('images')
    if len(uploads)>4:
        raise ValidationError('Upload at most four review images.')
    prepared = [prepare_image(file) for file in uploads]
    with transaction.atomic():
        OrderLine.objects.select_for_update().get(pk=line.pk)
        if Review.objects.filter(line=line).exists():
            raise ValidationError('This order item has already been reviewed.')
        review = Review(line=line,product=product,rating=int(data.get('rating',0)),title=data.get('title',''),
            text=data.get('text',''),display_name=line.order.recipient_name.split(' ')[0])
        review.full_clean()
        review.save()
        for image in prepared:
            ReviewImage.objects.create(review=review,source=image['source'],variants=image['variants'])
    return JsonResponse({'id':review.pk,'status':'pending',
        'images':[{'id':image.pk,'url':image.url} for image in review.images.all()]},status=201)


@api
@require_POST
def admin_action(request, public_id):
    staff(request)
    order = get_object_or_404(Order,public_id=public_id)
    data = payload(request)
    action = data.get('action')
    if action=='status':
        services.transition(order.pk,data.get('status'),request.user,data.get('reason',''))
    elif action=='cancel':
        services.request_cancel(order.pk,data.get('reason',''),request.user)
    elif action=='return':
        services.decide_return(order.pk,data.get('status'),data.get('reason',''),request.user,data.get('restock') is True)
    elif action=='pin':
        services.issue_delivery_pin(order.pk,request.user)
    elif action=='deliver':
        services.complete_delivery(order.pk,request.user,pin=data.get('pin',''),alternative_reason=data.get('reason',''))
    elif action=='assign':
        from django.contrib.auth import get_user_model
        driver = get_object_or_404(get_user_model(),pk=data.get('driver_id'),is_active=True,is_staff=True)
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order.pk)
            order.assigned_driver = driver
            services.emit(order,'assigned','Delivery assigned.',request.user)
    else:
        raise ValidationError('Invalid order action.')
    order.refresh_from_db()
    return JsonResponse(order_data(order))


@api
@require_POST
def driver_handover(request,public_id):
    if not request.user.is_authenticated or not request.user.is_staff:
        raise PermissionDenied
    order = get_object_or_404(Order,public_id=public_id,assigned_driver=request.user)
    data = payload(request)
    services.complete_delivery(order.pk,request.user,pin=data.get('pin',''))
    return JsonResponse({'delivered':True})


@api
@require_POST
def moderate_review(request,pk):
    staff(request,'orders.change_review')
    review = get_object_or_404(Review,pk=pk)
    data = payload(request)
    if data.get('status') not in ('approved','rejected','pending'):
        raise ValidationError('Invalid review decision.')
    review.status = data['status']
    review.moderation_reason = data.get('reason','')[:500]
    review.save(update_fields=['status','moderation_reason'])
    from .services import update_rating
    update_rating(review.product_id)
    return JsonResponse({'status':review.status})


@api
@require_http_methods(['POST','DELETE'])
def review_action(request,pk):
    review = get_object_or_404(Review.objects.select_related('line__order'),pk=pk)
    data = payload(request)
    if request.method == 'POST' and data.get('action') == 'report':
        if review.status != 'approved':
            raise Http404
        review.reported = True
        review.save(update_fields=['reported'])
        return JsonResponse({'reported':True})
    services.authorize(review.line.order,request.user,request.session)
    if request.method != 'DELETE' or review.status != 'pending':
        raise ValidationError('Photos can be removed while a review is pending moderation.')
    image = get_object_or_404(ReviewImage,pk=data.get('image_id'),review=review)
    image.delete()
    return JsonResponse({'deleted':True})


@api
@require_http_methods(['GET','POST'])
def notifications(request):
    if not request.user.is_authenticated:
        raise PermissionDenied
    queryset = Notification.objects.filter(event__order__customer=request.user)
    if request.method=='POST':
        queryset.filter(pk=payload(request).get('id')).update(read_at=timezone.now())
        return JsonResponse({'ok':True})
    return JsonResponse({'notifications':list(queryset.order_by('-event__created_at').values(
        'id','event__message','event__created_at','event__order__public_id','read_at')[:100])})
