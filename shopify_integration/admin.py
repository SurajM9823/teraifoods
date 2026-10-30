from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import transaction
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.html import format_html
from catalog.models import Product

from . import models
from .services import approve_variant_review, dry_run
from .draft_sync import prepare_draft
from .client import ShopifyError


class CustomShopifyAdmin(admin.ModelAdmin):
    """Keep Django's validated admin controls inside the store's staff layout."""
    change_list_template = 'admin/shopify_integration/change_list.html'
    change_form_template = 'admin/shopify_integration/change_form.html'
    object_history_template = 'admin/shopify_integration/object_history.html'
    delete_confirmation_template = 'admin/shopify_integration/delete_confirmation.html'
    delete_selected_confirmation_template = 'admin/shopify_integration/delete_selected_confirmation.html'


@admin.register(models.ShopifyCatalogueProduct)
class CatalogueAdmin(CustomShopifyAdmin):
    list_display = ('id', 'name', 'sku', 'regular_price', 'sale_price')
    search_fields = ('name', 'sku')
    list_filter = ('is_published', 'is_archived', 'category')
    actions = ('preview', 'queue_drafts', 'publish_products', 'unpublish_products')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_sync_permission(self, request):
        return request.user.has_perm('shopify_integration.sync_shopify_draft')

    def has_publication_permission(self, request):
        return request.user.has_perm('shopify_integration.publish_shopify_products')

    def channel_action(self, request, queryset, operation):
        from .publication import prepare_publication
        from .tasks import run_draft_job
        connection = models.ShopifyConnection.objects.filter(shop_domain=settings.SHOPIFY_SHOP_DOMAIN,enabled=True).first()
        if not connection or queryset.count()>20:
            self.message_user(request,'Configure a connection and select at most 20 products.',messages.ERROR)
            return
        if request.POST.get('confirm_channel_action')!='yes' or request.POST.get('reviewed')!='yes':
            return TemplateResponse(request,'admin/shopify_integration/confirm_publication.html',{
                **self.admin_site.each_context(request),
                'opts':self.model._meta,'operation':operation,
                'action_name':operation+'_products','products':list(queryset),
                'reports':[dry_run(p,connection) for p in queryset],'connection':connection,
                'title':'Confirm explicit Shopify '+operation})
        for product in queryset:
            try:
                job = prepare_publication(connection,product.pk,operation=operation,reviewed=True,actor=request.user)
            except ShopifyError as exc:
                self.message_user(request,f'Product {product.pk}: {exc}',messages.ERROR)
                continue
            # Durable pending jobs are also recovered by the dedicated queue dispatcher.
            def enqueue(pk=job.pk):
                try:
                    run_draft_job.apply_async(args=[pk],queue='shopify')
                except Exception:
                    self.message_user(request,f'Job {pk} saved; worker dispatcher will retry enqueueing.',messages.WARNING)
            transaction.on_commit(enqueue)
            self.message_user(request,f'Explicit {operation} job {job.pk} queued.')

    @admin.action(description='Publish selected products (requires confirmation)',permissions=['publication'])
    def publish_products(self,request,queryset):
        return self.channel_action(request,queryset,'publish')

    @admin.action(description='Unpublish selected products (requires confirmation)',permissions=['publication'])
    def unpublish_products(self,request,queryset):
        return self.channel_action(request,queryset,'unpublish')

    @admin.action(description='Dry-run selected products (no writes or network)')
    def preview(self, request, queryset):
        if queryset.count() > 20:
            self.message_user(request, 'Select at most 20 products.', messages.ERROR)
            return
        connection = models.ShopifyConnection.objects.filter(shop_domain=settings.SHOPIFY_SHOP_DOMAIN).first()
        return TemplateResponse(request, 'admin/shopify_integration/preview.html', {
            **self.admin_site.each_context(request), 'title': 'Shopify product preview',
            'reports': [dry_run(p, connection) for p in queryset],
        })

    @admin.action(description='Sync selected products (new products stay DRAFTS)', permissions=['sync'])
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
            self.message_user(request, f'Product {product.pk}: sync job {job.pk} queued. Publication state will be preserved.')


@admin.register(models.ShopifyConnection)
class ConnectionAdmin(CustomShopifyAdmin):
    list_display = ('shop_domain', 'enabled', 'api_version','import_orders_enabled')
    readonly_fields = ('order_sync_cursor','order_sync_after','order_sync_window_end','import_started_at')

    def save_model(self,request,obj,form,change):
        previous = models.ShopifyConnection.objects.filter(pk=obj.pk).first() if change else None
        if obj.import_orders_enabled and (not previous or not previous.import_orders_enabled):
            obj.order_sync_cursor = obj.import_started_at = timezone.now()
            obj.order_sync_after,obj.order_sync_window_end = '',None
        if not obj.enabled:
            obj.import_orders_enabled = False
        super().save_model(request,obj,form,change)


@admin.register(models.ChannelVariantDefinition)
class DefinitionAdmin(CustomShopifyAdmin):
    list_display = ('product', 'key', 'source_variant_id', 'price_policy', 'price')
    list_select_related = ('product',)
    search_fields = ('product__name', 'key')
    actions = ('preview', 'approve_review')

    @admin.action(description='Preview selected products (local JSON, no Shopify requests)')
    def preview(self, request, queryset):
        reports = [dry_run(product) for product in
                   Product.objects.filter(pk__in=queryset.values('product_id'))]
        return TemplateResponse(request, 'admin/shopify_integration/preview.html', {
            **self.admin_site.each_context(request), 'title': 'Shopify variant preview', 'reports': reports,
        })

    @admin.action(description='Approve complete normalized definitions for selected products', permissions=['change'])
    def approve_review(self, request, queryset):
        for pk in queryset.order_by().values_list('product_id', flat=True).distinct():
            try:
                approve_variant_review(pk, request.user)
            except ValidationError as exc:
                self.message_user(request, f'Product {pk}: ' + ', '.join(exc.messages), messages.ERROR)
            else:
                self.message_user(request, f'Product {pk}: variant review approved. No Shopify action performed.')


class ReadOnlyAdmin(CustomShopifyAdmin):
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


@admin.register(models.ShopifyWebhookReceipt)
class ReceiptAdmin(ReadOnlyAdmin):
    list_display = ('id','connection','topic','status','attempts','error_code','received_at')
    list_filter = ('status','topic')
    actions = ('retry_receipts',)

    def has_retry_permission(self,request):
        return request.user.has_perm('shopify_integration.change_shopifywebhookreceipt')

    @admin.action(description='Retry selected receipts using current Shopify data',permissions=['retry'])
    def retry_receipts(self,request,queryset):
        queryset.exclude(topic='app/uninstalled').update(status='pending',error_code='',next_retry_at=None)
        self.message_user(request,'Receipts queued for retry when order import is enabled.')


@admin.register(models.ShopifyOrderMapping)
class ImportedOrderAdmin(ReadOnlyAdmin):
    list_display = ('remote_order_name','remote_order_gid','connection','status','error_code','local_order','remote_updated_at')
    list_filter = ('status','connection')
    search_fields = ('remote_order_name','remote_order_gid')
    exclude = ('payload_encrypted',)
    actions = ('retry_imports',)

    @admin.display(description='Django order')
    def local_order(self,obj):
        return format_html('<a href="/admin/orders/{}/">{}</a>',obj.order.public_id,obj.order.number) if obj.order_id else 'Quarantined — no operational order created'

    def has_retry_permission(self,request):
        return request.user.has_perm('shopify_integration.change_shopifyordermapping')

    @admin.action(description='Re-fetch and retry selected Shopify orders',permissions=['retry'])
    def retry_imports(self,request,queryset):
        from .tasks import retry_order_mapping
        if queryset.count()>20:
            self.message_user(request,'Select at most 20 orders.',messages.ERROR)
            return
        for mapping in queryset:
            retry_order_mapping.apply_async(args=[mapping.pk],queue='shopify')
        self.message_user(request,'Selected orders queued for current-state reconciliation.')


for model in (models.VariantReview, models.ShopifyVariantMapping,
              models.ShopifyMediaMapping, models.ShopifyOrderLineMapping):
    admin.site.register(model, ReadOnlyAdmin)
