from django.db import migrations


def install(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("""
            CREATE FUNCTION catalog_stockaudit_immutable() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'Stock audit records are immutable';
            END;
            $$ LANGUAGE plpgsql;
            CREATE TRIGGER catalog_stockaudit_immutable
            BEFORE UPDATE OR DELETE ON catalog_stockaudit
            FOR EACH ROW EXECUTE FUNCTION catalog_stockaudit_immutable();
        """)


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS catalog_stockaudit_immutable ON catalog_stockaudit;
            DROP FUNCTION IF EXISTS catalog_stockaudit_immutable();
        """)


class Migration(migrations.Migration):
    dependencies = [('catalog', '0005_catalogrevision')]
    operations = [migrations.RunPython(install, uninstall)]
