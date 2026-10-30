from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('shopify_integration', '0002_allow_local_image_deletion')]
    operations = [migrations.CreateModel(
        name='ShopifyCatalogueProduct', fields=[],
        options={'proxy': True, 'verbose_name': 'Shopify catalogue product',
                 'permissions': [('sync_shopify_draft', 'Can synchronize Shopify drafts')],
                 'indexes': [], 'constraints': []},
        bases=('catalog.product',),
    )]
