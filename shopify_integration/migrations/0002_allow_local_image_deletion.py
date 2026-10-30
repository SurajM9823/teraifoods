import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('shopify_integration', '0001_initial')]

    operations = [
        migrations.AlterField(
            model_name='channelvariantdefinition', name='image',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    to='catalog.productimage'),
        ),
        migrations.AlterField(
            model_name='shopifymediamapping', name='image',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    to='catalog.productimage'),
        ),
    ]
