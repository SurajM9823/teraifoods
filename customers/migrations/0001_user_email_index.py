from django.conf import settings
from django.db import migrations


def add_index(apps, schema_editor):
    user = apps.get_model(settings.AUTH_USER_MODEL)
    table = schema_editor.quote_name(user._meta.db_table)
    schema_editor.execute(f'CREATE INDEX IF NOT EXISTS terai_user_email_idx ON {table} (email)')


def remove_index(apps, schema_editor):
    schema_editor.execute('DROP INDEX IF EXISTS terai_user_email_idx')


class Migration(migrations.Migration):
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.RunPython(add_index, remove_index)]
