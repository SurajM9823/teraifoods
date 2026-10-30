from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from catalog.models import Product
from .models import IntegrationLog, ShopifyProductMapping, VariantReview
from .normalization import MANAGED_FIELDS, normalize_product, variant_fingerprint

def dry_run(product, connection=None):
    """Local comparison to last applied snapshot, never a claim about live Shopify state."""
    report = normalize_product(product)
    mapping = ShopifyProductMapping.objects.filter(connection=connection, product=product).first() if connection else None
    previous = mapping.applied_payload if mapping else {}
    changed = [field for field in MANAGED_FIELDS if report['payload'][field] != previous.get(field)]
    report.update({
        'dry_run': True, 'remote_checked': False,
        'comparison_basis': 'last_applied_snapshot' if previous else 'no_applied_snapshot',
        'managed_fields': list(MANAGED_FIELDS),
        'expected_changes': [{'field': field, 'before': previous.get(field), 'after': report['payload'][field]} for field in changed],
        'proposed_action': 'blocked' if report['errors'] else ('update_managed_fields' if mapping and mapping.remote_product_gid else 'create_draft'),
        'new_product_status': 'DRAFT', 'publishing': 'requires_separate_explicit_action',
        'unpublishing': 'requires_separate_explicit_action', 'inventory_quantity_sync': False,
        'warnings': ['Local preview only; remote drift has not been checked.',
                     'Catalogue execution, publication and order import use separate configured controls.'],
    })
    return report


@transaction.atomic
def approve_variant_review(product_id, actor):
    if not actor.is_active or not actor.is_staff or not actor.has_perm('shopify_integration.change_channelvariantdefinition'):
        raise PermissionDenied
    product = Product.objects.select_for_update().get(pk=product_id)
    definitions = list(product.channel_variants.select_for_update().order_by('key'))
    report = normalize_product(product, require_review=False)
    if report['kind'] != 'variant' or report['errors']:
        raise ValidationError(report['errors'] or ['No variant definitions to review.'])
    review, _ = VariantReview.objects.update_or_create(product=product, defaults={
        'fingerprint': variant_fingerprint(product, definitions), 'reviewed_by': actor,
    })
    IntegrationLog.objects.create(product=product, operation='variant_review', status='approved')
    return review
