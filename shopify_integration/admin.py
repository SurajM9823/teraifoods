from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.conf import settings
from django.db import transaction
from catalog.models import Product

from . import models
from .services import approve_variant_review, dry_run
from .draft_sync import prepare_draft
from .client import ShopifyError


@admin.register(models.ShopifyCatalogueProduct)
class CatalogueAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'sku', 'regular_price', 'sale_price')
    search_fields = ('name', 'sku')
    list_filter = ('is_published', 'is_archived', 'category')
    actions = ('preview', 'queue_drafts')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_sync_permission(self, request):
        return request.user.has_perm('shopify_integration.sync_shopify_draft')

    @admin.action(description='Dry-run selected products (no writes or network)')
    def preview(self, request, queryset):
        import json
        if queryset.count() > 20:
            self.message_user(request, 'Select at most 20 products.', messages.ERROR)
            return
        connection = models.ShopifyConnection.objects.filter(shop_domain=settings.SHOPIFY_SHOP_DOMAIN).first()
        return HttpResponse(json.dumps([dry_run(p, connection) for p in queryset], indent=2), content_type='application/json')

    @admin.action(description='Sync selected products as Shopify DRAFTS', permissions=['sync'])
    def queue_drafts(self, request, queryset):
        from .tasks import run_draft_job
        connection = models.ShopifyConnection.objects.filter(shop_domain=settings.SHOPIFY_SHOP_DOMAIN, enabled=True).first()
        if not connection or queryset.count() > 20:
            self.message_user(request, 'Select at most 20 products and configure an enabled connection.', messages.ERROR)
            return
        for product in queryset:
            try:
                job = prepare_draft(connection, product.pk, actor=request.user)
            except (ValidationError, ShopifyError) as exc:
                self.message_user(request, f'Product {product.pk}: {exc}', messages.ERROR)
                continue
            def enqueue(pk=job.pk):
                try:
                    run_draft_job.apply_async(args=[pk], queue='shopify')
                except Exception:
                    # The durable job will be picked up by the dedicated queue's periodic dispatcher.
                    models.IntegrationLog.objects.create(operation='enqueue_draft', status='queued', codes=['broker_unavailable'])
            transaction.on_commit(enqueue)
            self.message_user(request, f'Product {product.pk}: draft job {job.pk} queued. Nothing will be published.')


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


@admin.register(models.ShopifyProductMapping)
class ProductMappingAdmin(ReadOnlyAdmin):
    list_display = ('product', 'connection', 'status', 'error_code', 'remote_product_gid', 'updated_at')
    list_filter = ('status', 'connection')
    list_select_related = ('product', 'connection')
    search_fields = ('product__name', 'remote_product_gid')


@admin.register(models.ShopifySyncJob)
class JobAdmin(ReadOnlyAdmin):
    list_display = ('id', 'mapping', 'operation', 'status', 'attempts', 'error_code', 'next_retry_at')
    list_filter = ('status', 'operation')
    list_select_related = ('mapping',)


for model in (models.VariantReview, models.ShopifyVariantMapping,
              models.ShopifyMediaMapping, models.ShopifyWebhookReceipt,
              models.ShopifyOrderMapping, models.ShopifyOrderLineMapping):
    admin.site.register(model, ReadOnlyAdmin)
