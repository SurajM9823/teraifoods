from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from catalog.models import Order
from . import services
from .models import Review


@never_cache
@staff_member_required(login_url='/admin/login')
def index(request):
    if not request.user.has_perm('catalog.view_order'):
        raise PermissionDenied
    rows = Order.objects.prefetch_related('lines').order_by('-created_at')
    if request.GET.get('q'):
        q = request.GET['q'][:150]
        number = q.upper().removeprefix('TF-')
        condition = Q(email__icontains=q) | Q(recipient_name__icontains=q)
        if number.isdigit():
            condition |= Q(pk=int(number))
        rows = rows.filter(condition)
    if request.GET.get('status'):
        rows = rows.filter(fulfilment_status=request.GET['status'])
    summary = dict(total_orders=rows.count(),
        processing=rows.filter(fulfilment_status__in=['placed','confirmed','preparing','ready_for_dispatch']).count(),
        dispatched=rows.filter(fulfilment_status__in=['dispatched','out_for_delivery']).count(),
        total_revenue='£'+str(rows.filter(payment_status='paid').aggregate(total=Sum('total'))['total'] or '0.00'))
    page = Paginator(rows, 30).get_page(request.GET.get('page'))
    formatted = [dict(id=o.number,public_id=o.public_id,customer=o.recipient_name or 'Legacy order',email=o.email,
        type='Registered' if o.customer_id else 'Guest',items_summary=', '.join(f'{i.product_name} × {i.quantity}' for i in o.lines.all()),
        total='£'+str(o.total),payment_status=o.payment_status.title(),
        fulfillment_status=o.fulfilment_status.replace('_',' ').title(),date=o.created_at) for o in page]
    return render(request,'web/backoffice/orders.html',dict(active_page='orders',orders_list=formatted,summary=summary,page=page))


@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['GET','POST'])
def detail(request,public_id):
    if not request.user.has_perm('catalog.view_order'):
        raise PermissionDenied
    order = get_object_or_404(Order,public_id=public_id)
    if request.method == 'POST':
        if not request.user.has_perm('catalog.change_order'):
            raise PermissionDenied
        action = request.POST.get('action')
        try:
            if action == 'status':
                services.transition(order.pk,request.POST.get('status'),request.user,request.POST.get('reason',''))
            elif action == 'cancel':
                services.request_cancel(order.pk,request.POST.get('reason',''),request.user)
            elif action == 'pin':
                services.issue_delivery_pin(order.pk,request.user)
            elif action == 'deliver':
                services.complete_delivery(order.pk,request.user,pin=request.POST.get('pin',''),
                    alternative_reason=request.POST.get('reason',''))
            elif action == 'return':
                services.decide_return(order.pk,request.POST.get('status'),request.POST.get('reason',''),
                    request.user,restock=request.POST.get('restock')=='on')
            elif action == 'support_reply':
                services.support_message(order.pk,request.POST.get('reason',''),request.user,reply=True)
            elif action == 'tracking':
                from django.core.validators import URLValidator
                from django.db import transaction
                url = request.POST.get('tracking_url','').strip()
                if url:
                    URLValidator(schemes=['https'])(url)
                driver_id = request.POST.get('driver')
                driver = get_object_or_404(get_user_model(),pk=driver_id,is_active=True,is_staff=True) if driver_id else None
                with transaction.atomic():
                    locked = Order.objects.select_for_update().get(pk=order.pk)
                    locked.tracking_reference = request.POST.get('tracking_reference','')[:150]
                    locked.tracking_url = url
                    locked.assigned_driver = driver
                    services.emit(locked,'tracking_updated','Delivery tracking updated.',request.user)
            else:
                raise ValidationError('Choose an order action.')
        except ValidationError as exc:
            messages.error(request,' '.join(exc.messages))
        else:
            messages.success(request,'Order updated.')
        return redirect('order-admin-detail',public_id=public_id)
    return render(request,'orders/admin_detail.html',dict(active_page='orders',order=order,
        statuses=sorted(services.TRANSITIONS.get(order.fulfilment_status,set())-{'cancelled'}),
        drivers=get_user_model().objects.filter(is_staff=True,is_active=True)))


@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['GET','POST'])
def reviews(request):
    if not request.user.has_perm('orders.view_review'):
        raise PermissionDenied
    if request.method == 'POST':
        if not request.user.has_perm('orders.change_review'):
            raise PermissionDenied
        review = get_object_or_404(Review,pk=request.POST.get('id'))
        if request.POST.get('status') in ('approved','rejected','pending'):
            review.status = request.POST['status']
            review.moderation_reason = request.POST.get('reason','')[:500]
            review.save(update_fields=['status','moderation_reason'])
            services.update_rating(review.product_id)
            messages.success(request,'Review moderation saved.')
        return redirect('order-admin-reviews')
    page = Paginator(Review.objects.select_related('product').prefetch_related('images').order_by('-created_at'),30).get_page(request.GET.get('page'))
    return render(request,'orders/admin_reviews.html',{'reviews':page,'active_page':'orders'})
