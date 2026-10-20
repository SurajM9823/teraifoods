import uuid
from django.db import migrations


def populate(apps, schema_editor):
    Order = apps.get_model('catalog', 'Order')
    alias = schema_editor.connection.alias
    for order in Order.objects.using(alias).filter(public_id__isnull=True).iterator():
        Order.objects.using(alias).filter(pk=order.pk).update(public_id=uuid.uuid4(),
            payment_status='unknown',fulfilment_status='cancelled' if order.status=='cancelled' else 'legacy_reserved')


class Migration(migrations.Migration):
    dependencies = [('catalog','0010_product_review_count')]
    operations = [migrations.RunPython(populate,migrations.RunPython.noop)]
