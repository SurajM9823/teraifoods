"""Validated, content-addressed image files using the configured Django storage."""
import hashlib
import io
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from .models import Product, ProductImage

FORMATS = {'JPEG', 'PNG', 'WEBP', 'AVIF'}
MAX_BYTES = 15 * 1024 * 1024


def media_url(path):
    cdn = getattr(settings, 'PRODUCT_CDN_URL', '').rstrip('/')
    return f'{cdn}/{path}' if cdn else default_storage.url(path)


def _save(path, data):
    if not default_storage.exists(path):
        # A concurrent writer may choose a suffixed filename. Always retain the
        # actual returned storage name, never claim a filename that wasn't saved.
        return default_storage.save(path, ContentFile(data))
    return path


def prepare_image(upload):
    raw = upload.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValidationError('Images must be no larger than 15 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as probe:
                if probe.format not in FORMATS or getattr(probe, 'n_frames', 1) != 1:
                    raise ValidationError('Use a still JPEG, PNG, WebP or AVIF image.')
                probe.verify()
            with Image.open(io.BytesIO(raw)) as opened:
                opened.load()
                source = ImageOps.exif_transpose(opened).convert('RGB')
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValidationError('Invalid or excessively large image content.') from exc
    digest = hashlib.sha256(raw).hexdigest()
    root = f'products/{digest}'
    variants = {}
    for fmt in ('AVIF', 'WEBP', 'JPEG'):
        variants[fmt.lower()] = {}
        for size in (160, 320, 500, 800, 1200):
            image = source.copy()
            image.thumbnail((size, size), Image.Resampling.LANCZOS)
            width = str(image.width)
            if width in variants[fmt.lower()]:
                continue
            output = io.BytesIO()
            image.save(output, format=fmt, quality=88)
            extension = 'jpg' if fmt == 'JPEG' else fmt.lower()
            variants[fmt.lower()][width] = _save(f'{root}/{image.width}.{extension}', output.getvalue())
    return dict(source=list(variants['jpeg'].values())[-1], variants=variants,
                digest=digest, width=source.width, height=source.height)


def add_image(product_id, upload, *, alt='', main=False):
    prepared = prepare_image(upload)
    with transaction.atomic():
        product = Product.objects.select_for_update().get(pk=product_id)
        count = product.images.count()
        if count >= 5:
            raise ValidationError('A product may have at most five images.')
        if main:
            product.images.filter(is_main=True).update(is_main=False)
        return ProductImage.objects.create(product=product, alt=alt or product.name,
                                           position=count, is_main=main or count == 0, **prepared)
