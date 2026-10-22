"""Persistent wholesale enquiries; quotes do not reserve stock or take payment."""
import hashlib
import json
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST
from .models import BulkRequest, BulkReply
from .views import api, payload

STATES = {'new': {'under_review','quoted','rejected'}, 'under_review': {'quoted','rejected'},
          'quoted': {'under_review','accepted','rejected'}, 'accepted': {'processing','cancelled'},
          'processing': {'dispatched','cancelled'}, 'dispatched': {'completed'},
          'completed': set(), 'rejected': set(), 'cancelled': set()}


def token(row):
    return signing.dumps(str(row.public_id), salt='bulk-request-access')


def grant(session, row):
    grants=session.get('bulk_grants',{})
    grants[str(row.public_id)]=(timezone.now()+timedelta(days=30)).timestamp()
    session['bulk_grants']=dict(list(grants.items())[-50:])


def permitted(request):
    grants=[key for key,expiry in request.session.get('bulk_grants',{}).items() if expiry>timezone.now().timestamp()]
    condition=Q(public_id__in=grants)
    if request.user.is_authenticated:
        condition |= Q(customer=request.user)
    return BulkRequest.objects.filter(condition)


def data(row):
    return dict(id=str(row.public_id),number=row.number,company=row.company,contact_name=row.contact_name,
        email=row.email,phone=row.phone,address=row.address,city_postcode=row.city_postcode,
        requested_date=row.requested_date,items=row.items,notes=row.notes,status=row.status,
        quoted_total=str(row.quoted_total) if row.quoted_total is not None else None,
        delivery_terms=row.delivery_terms,payment_terms=row.payment_terms,created_at=row.created_at,
        replies=[dict(message=r.message,status=r.status,quote=r.quote,created_at=r.created_at)
                 for r in row.replies.order_by('pk')])


def text(body,key,limit,required=True):
    value=body.get(key,'')
    if not isinstance(value,str) or len(value)>limit or (required and not value.strip()):
        raise ValidationError(f'Enter a valid {key.replace("_"," ")} (up to {limit} characters).')
    return value.strip()


def amount(value):
    try:
        number=Decimal(str(value))
        if not number.is_finite() or number<0 or number>Decimal('999999999999.99') or number != number.quantize(Decimal('.01')):
            raise ValueError
        return number
    except (InvalidOperation,ValueError):
        raise ValidationError('Enter a non-negative GBP amount with at most two decimal places.')


@api
@require_http_methods(['GET','POST'])
def requests(request):
    if request.method=='GET':
        page=Paginator(permitted(request).prefetch_related('replies').order_by('-created_at'),20).get_page(request.GET.get('page'))
        return JsonResponse({'requests':[data(row) for row in page],'has_more':page.has_next()})
    body=payload(request)
    values={key:text(body,key,limit) for key,limit in [('company',150),('contact_name',150),('email',254),
        ('phone',30),('address',500),('city_postcode',150)]}
    validate_email(values['email'])
    if not re.fullmatch(r'(?:\+44|0044|0)[0-9]{9,10}',re.sub(r'[\s().-]','',values['phone'])):
        raise ValidationError('Enter a valid UK contact number.')
    postcode=re.search(r'([A-Z]{1,2}[0-9][A-Z0-9]?\s*[0-9][A-Z]{2})$',values['city_postcode'].upper())
    if not postcode or postcode.group(1).startswith(('JE','GY','IM')):
        raise ValidationError('Enter the delivery town/city and a UK postcode.')
    values['notes']=text(body,'notes',3000,False)
    when=text(body,'requested_date',10,False)
    values['requested_date']=date.fromisoformat(when) if when else None
    if values['requested_date'] and values['requested_date']<timezone.localdate():
        raise ValidationError('Requested delivery date cannot be in the past.')
    items=body.get('items')
    if not isinstance(items,list) or not 1<=len(items)<=100:
        raise ValidationError('Enter between 1 and 100 product lines.')
    values['items']=[]
    for item in items:
        if not isinstance(item,dict) or type(item.get('quantity')) is not int or not 1<=item['quantity']<=100000:
            raise ValidationError('Each line needs a whole quantity between 1 and 100000.')
        values['items'].append(dict(description=text(item,'description',300),sku=text(item,'sku',100,False),
            unit=text(item,'unit',100,False),quantity=item['quantity'],
            requested_price=str(amount(item.get('requested_price',0)))))
    key=request.headers.get('Idempotency-Key','')
    if not 1<=len(key)<=100:
        raise ValidationError('A submission key is required.')
    if not request.session.session_key:
        request.session.create()
    scope=f'user:{request.user.pk}' if request.user.is_authenticated else request.session.session_key
    scoped=hashlib.sha256(f'{scope}:{key}'.encode()).hexdigest()
    digest=hashlib.sha256(json.dumps(values,sort_keys=True,default=str).encode()).hexdigest()
    with transaction.atomic():
        row,created=BulkRequest.objects.get_or_create(submission_key=scoped,defaults={**values,'digest':digest,
            'customer':request.user if request.user.is_authenticated else None})
        if row.digest!=digest:
            raise ValidationError('Submission changed. Start a new request.')
        if created:
            BulkReply.objects.create(request=row,message='Request received. The store will review your requirements and reply here.',status='new')
    grant(request.session,row)
    return JsonResponse({'request':data(row),'tracking_url':f'/bulk-order/?request={row.public_id}#access={token(row)}'},status=201 if created else 200)


@api
@require_POST
def access(request):
    try:
        public_id=signing.loads(payload(request).get('token',''),salt='bulk-request-access',max_age=30*86400)
        row=BulkRequest.objects.get(public_id=public_id)
    except (signing.BadSignature,BulkRequest.DoesNotExist,ValueError,ValidationError):
        raise PermissionDenied
    grant(request.session,row)
    return JsonResponse(data(row))


@api
@require_http_methods(['GET'])
def detail(request,public_id):
    return JsonResponse(data(get_object_or_404(permitted(request),public_id=public_id)))


@never_cache
@staff_member_required(login_url='/admin/login')
def admin_index(request):
    if not request.user.has_perm('orders.view_bulkrequest'):
        raise PermissionDenied
    rows=BulkRequest.objects.order_by('-created_at')
    if request.GET.get('status'):
        rows=rows.filter(status=request.GET['status'])
    if request.GET.get('q'):
        q=request.GET['q'][:150]
        condition=Q(company__icontains=q)|Q(email__icontains=q)|Q(contact_name__icontains=q)
        number=q.upper().removeprefix('TF-BQ-')
        if number.isdigit(): condition |= Q(pk=int(number))
        rows=rows.filter(condition)
    return render(request,'orders/bulk_admin_list.html',{'page':Paginator(rows,30).get_page(request.GET.get('page')),
        'statuses':STATES,'active_page':'bulk-orders'})


@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['GET','POST'])
def admin_detail(request,public_id):
    if not request.user.has_perm('orders.view_bulkrequest'):
        raise PermissionDenied
    row=get_object_or_404(BulkRequest,public_id=public_id)
    if request.method=='POST':
        if not request.user.has_perm('orders.change_bulkrequest'):
            raise PermissionDenied
        try:
            with transaction.atomic():
                row=BulkRequest.objects.select_for_update().get(pk=row.pk)
                if request.POST.get('version')!=str(row.replies.count()):
                    raise ValidationError('This request was updated. Review the latest response before saving again.')
                target=request.POST.get('status')
                if target!=row.status and target not in STATES.get(row.status,set()):
                    raise ValidationError('Choose a valid next status.')
                message=text(request.POST,'message',3000)
                delivery=text(request.POST,'delivery_terms',2000,False)
                payment=text(request.POST,'payment_terms',2000,False)
                raw=request.POST.get('quoted_total','').strip()
                quoted=amount(raw) if raw else None
                if target in ('quoted','accepted','processing','dispatched','completed') and (quoted is None or not delivery or not payment):
                    raise ValidationError('A quote needs a total, delivery terms and payment terms.')
                row.status,row.quoted_total,row.delivery_terms,row.payment_terms=target,quoted,delivery,payment
                row.save()
                BulkReply.objects.create(request=row,actor=request.user,message=message,status=target,
                    quote={'total':str(quoted) if quoted is not None else None,'delivery':delivery,'payment':payment})
            messages.success(request,'Response saved. The customer can see it now; email is queued.')
            return redirect('bulk-admin-detail',public_id=public_id)
        except ValidationError as exc:
            messages.error(request,' '.join(exc.messages))
            row.refresh_from_db()
    return render(request,'orders/bulk_admin_detail.html',{'inquiry':row,'version':row.replies.count(),
        'statuses':[row.status]+sorted(STATES.get(row.status,set())),'active_page':'bulk-orders'})
