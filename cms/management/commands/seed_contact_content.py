from importlib import import_module
from django.apps import apps
from django.db import connection
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Add missing initial contact content without overwriting edits or creating demo enquiries.'

    def handle(self, *args, **options):
        with connection.schema_editor() as editor:
            import_module('cms.migrations.0005_contact_content').seed(apps, editor)
        self.stdout.write(self.style.SUCCESS('Missing contact content added. Existing edits preserved.'))
