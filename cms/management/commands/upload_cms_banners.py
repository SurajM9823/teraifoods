from pathlib import Path
from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from cms.models import Banner


class Command(BaseCommand):
    help = 'Copy bundled starter banners into organized server media storage.'

    def handle(self, **options):
        for banner in Banner.objects.filter(image='').exclude(fallback_image=''):
            path = settings.BASE_DIR / 'web' / 'static' / 'web' / 'images' / Path(banner.fallback_image).name
            with path.open('rb') as source:
                banner.image.save(path.name, File(source), save=True)
            self.stdout.write(f'Uploaded banner {banner.pk}')
