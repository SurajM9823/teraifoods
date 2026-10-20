from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.db import transaction, IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .forms import DeliveryPolicyForm, WeightBandForm
from .models import DeliveryPolicy, WeightBand


@never_cache
@staff_member_required(login_url='/admin/login')
@require_http_methods(['GET', 'HEAD', 'POST'])
def settings_view(request):
    if not request.user.has_perm('delivery.view_weightband'):
        raise PermissionDenied
    policy = DeliveryPolicy.objects.filter(pk=1).first() or DeliveryPolicy(pk=1)
    instance = get_object_or_404(WeightBand, pk=request.GET['edit']) if request.GET.get('edit', '').isdigit() else None
    policy_form, band_form = DeliveryPolicyForm(instance=policy), WeightBandForm(instance=instance)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'policy':
            if not request.user.has_perm('delivery.change_deliverypolicy'):
                raise PermissionDenied
            policy_form = DeliveryPolicyForm(request.POST, instance=policy)
            if policy_form.is_valid():
                policy_form.save()
                messages.success(request, 'Delivery estimate updated.')
                return redirect('delivery:settings')
        elif action == 'band':
            if not request.user.has_perm('delivery.change_weightband' if instance else 'delivery.add_weightband'):
                raise PermissionDenied
            band_form = WeightBandForm(request.POST, instance=instance)
            if band_form.is_valid():
                try:
                    with transaction.atomic():
                        band_form.save()
                except IntegrityError:
                    band_form.add_error(None, 'This weight limit already exists. Refresh and retry.')
                else:
                    messages.success(request, 'Delivery weight band saved.')
                    return redirect('delivery:settings')
        else:
            messages.error(request, 'Choose a delivery settings action.')
    return render(request, 'delivery/settings.html', dict(active_page='delivery', policy_form=policy_form,
        band_form=band_form, bands=WeightBand.objects.all(), editing=instance))
