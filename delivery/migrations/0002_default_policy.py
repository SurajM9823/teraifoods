from django.db import migrations


def seed(apps, schema_editor):
    apps.get_model('delivery', 'DeliveryPolicy').objects.using(schema_editor.connection.alias).get_or_create(
        pk=1, defaults={'minimum_days':2, 'maximum_days':4})


class Migration(migrations.Migration):
    dependencies = [('delivery','0001_initial')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
