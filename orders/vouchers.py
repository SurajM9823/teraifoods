import secrets
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Voucher, VoucherUse
from .channels import require_website_order


def validate(code, email, *, lock=False):
    if not isinstance(code,str) or not isinstance(email,str):
        raise ValidationError('Enter a voucher and its original email address.')
    rows=Voucher.objects.select_for_update() if lock else Voucher.objects
    voucher=rows.filter(code=code.strip().upper(),email__iexact=email.strip()).first()
    if not voucher or voucher.redeemed_at or voucher.reserved_order_id:
        raise ValidationError('Voucher invalid, used, or reserved by another checkout. Use its original email address.')
    return voucher


def issue(order, amount):
    require_website_order(order)
    return Voucher.objects.get_or_create(source_order=order,defaults={'code':'TF-'+secrets.token_hex(12).upper(),'amount':amount,'email':order.email})[0]


def reserve(order, voucher):
    require_website_order(order)
    value=min(voucher.amount,order.total)
    VoucherUse.objects.create(order=order,voucher=voucher,amount=value)
    voucher.reserved_order=order;voucher.save(update_fields=['reserved_order'])
    order.total-=value;order.save(update_fields=['total'])


def consume(order):
    require_website_order(order)
    Voucher.objects.filter(reserved_order=order,redeemed_at__isnull=True).update(redeemed_at=timezone.now())


def release(order):
    require_website_order(order)
    Voucher.objects.filter(reserved_order=order,redeemed_at__isnull=True).update(reserved_order=None)


def applied(order):
    return order.voucher_use.amount if hasattr(order,'voucher_use') else Decimal('0')
