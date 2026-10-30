from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from catalog.models import Product

from . import models
from .services import approve_variant_review, dry_run


@admin.register(models.ShopifyConnection)
class ConnectionAdmin(admin.ModelAdmin):
    list_display = ('shop_domain', 'enabled', 'api_version')


@admin.register(models.ChannelVariantDefinition)
class DefinitionAdmin(admin.ModelAdmin):
    list_display = ('product', 'key', 'source_variant_id', 'price_policy', 'price')
    list_select_related = ('product',)
    search_fields = ('product__name', 'key')
    actions = ('preview', 'approve_review')

    @admin.action(description='Preview selected products (local JSON, no Shopify requests)')
    def preview(self, request, queryset):
        import json
        reports = [dry_run(product) for product in
                   Product.objects.filter(pk__in=queryset.values('product_id'))]
        return HttpResponse(json.dumps(reports, indent=2), content_type='application/json')

    @admin.action(description='Approve complete normalized definitions for selected products', permissions=['change'])
    def approve_review(self, request, queryset):
        for pk in queryset.order_by().values_list('product_id', flat=True).distinct():
            try:
                approve_variant_review(pk, request.user)
            except ValidationError as exc:
                self.message_user(request, f'Product {pk}: ' + ', '.join(exc.messages), messages.ERROR)
            else:
                self.message_user(request, f'Product {pk}: variant review approved. No Shopify action performed.')


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.IntegrationLog)
class LogAdmin(ReadOnlyAdmin):
    list_display = ('created_at', 'product', 'operation', 'status', 'codes')
    list_filter = ('operation', 'status')


for model in (models.VariantReview, models.ShopifyProductMapping, models.ShopifyVariantMapping,
              models.ShopifyMediaMapping, models.ShopifySyncJob, models.ShopifyWebhookReceipt,
              models.ShopifyOrderMapping, models.ShopifyOrderLineMapping):
    admin.site.register(model, ReadOnlyAdmin)
