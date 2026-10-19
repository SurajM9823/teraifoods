"""One shared public payload; versioned keys prevent refill/invalidation races."""
import logging
import uuid
from contextlib import nullcontext

from django.core.cache import cache
from redis.exceptions import RedisError
from .models import Banner, InformationBlock

logger = logging.getLogger(__name__)
GENERATION_KEY = 'cms:home:generation:v1'
TTL = 300
CACHE_ERRORS = (RedisError, ConnectionError, TimeoutError, OSError)


def invalidate_home():
    try:
        cache.set(GENERATION_KEY, uuid.uuid4().hex, timeout=None)
    except CACHE_ERRORS:
        # Old payloads expire within five minutes if Redis is unavailable at save.
        logger.exception('CMS cache invalidation unavailable')


def _load():
    return {
        'banners': [dict(title=b.title, badge=b.badge, description=b.description,
                         image_url=b.image_url, image_alt=b.image_alt,
                         button_label=b.button_label, destination=b.destination)
                    for b in Banner.objects.filter(is_active=True)],
        'information': {b.slot: dict(title=b.title, description=b.description)
                        for b in InformationBlock.objects.filter(is_active=True)},
    }


def homepage_content():
    try:
        generation = cache.get(GENERATION_KEY)
        if generation is None:
            cache.add(GENERATION_KEY, uuid.uuid4().hex, timeout=None)
            generation = cache.get(GENERATION_KEY)
        key = f'cms:home:v1:{generation}'
        value = cache.get(key)
        if value is not None:
            return value
        # Redis lock coalesces concurrent cold requests across web processes.
        lock = cache.lock(f'{key}:lock', timeout=30, blocking_timeout=10) if hasattr(cache, 'lock') else nullcontext()
        with lock:
            value = cache.get(key)
            if value is None:
                value = _load()
                cache.set(key, value, timeout=TTL)
            return value
    except CACHE_ERRORS:
        logger.warning('CMS cache unavailable; reading content from database')
        return _load()
