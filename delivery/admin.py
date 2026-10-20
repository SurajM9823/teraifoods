from django.contrib import admin
from .models import WeightBand, DeliveryPolicy
from .forms import WeightBandForm, DeliveryPolicyForm


@admin.register(WeightBand)
class WeightBandAdmin(admin.ModelAdmin):
    form = WeightBandForm
    list_display = ('max_weight_grams', 'charge', 'is_active')
    list_filter = ('is_active',)


@admin.register(DeliveryPolicy)
class DeliveryPolicyAdmin(admin.ModelAdmin):
    form = DeliveryPolicyForm

    def has_add_permission(self, request):
        return super().has_add_permission(request) and not DeliveryPolicy.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
