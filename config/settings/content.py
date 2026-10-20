"""CMS uploads live on the server; public content is cached in Redis."""
import os
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755

# Optional CDN origin mapped to MEDIA_ROOT. URLs include content hashes.
PRODUCT_CDN_URL = os.getenv('PRODUCT_CDN_URL', '')
