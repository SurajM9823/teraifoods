"""Shared active category tree, ready for catalog consumers."""
import logging
import uuid
from contextlib import nullcontext
from django.core.cache import cache
from django.db.models import Prefetch
from redis.exceptions import RedisError
from .models import Category, Subcategory

GENERATION_KEY = 'catalog:categories:generation:v1'
CACHE_ERRORS = (RedisError, ConnectionError, TimeoutError, OSError)
logger = logging.getLogger(__name__)


def invalidate_categories():
    try:
        cache.set(GENERATION_KEY, uuid.uuid4().hex, timeout=None)
    except CACHE_ERRORS:
        logger.warning('Category cache invalidation unavailable; payload expires within five minutes')


def _load():
    categories = Category.objects.filter(is_active=True).prefetch_related(
        Prefetch('subcategories', queryset=Subcategory.objects.filter(is_active=True)))
    def item(category):
        return dict(id=category.pk, name=category.name, slug=category.slug,
                    description=category.description, icon=category.icon)
    return [dict(**item(category), subcategories=[item(child) for child in category.subcategories.all()])
            for category in categories]


def category_tree():
    try:
        generation = cache.get(GENERATION_KEY)
        if generation is None:
            cache.add(GENERATION_KEY, uuid.uuid4().hex, timeout=None)
            generation = cache.get(GENERATION_KEY)
        key = f'catalog:categories:v1:{generation}'
        result = cache.get(key)
        if result is not None:
            return result
        lock = cache.lock(f'{key}:lock', timeout=30, blocking_timeout=10) if hasattr(cache, 'lock') else nullcontext()
        with lock:
            result = cache.get(key)
            if result is None:
                result = _load()
                cache.set(key, result, timeout=300)
            return result
    except CACHE_ERRORS:
        logger.warning('Category cache unavailable; reading database')
        return _load()
