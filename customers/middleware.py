"""Fail closed on unavailable rate-limit storage and bound authentication traffic."""
import hashlib
import logging

from allauth.core.internal.httpkit import get_client_ip
from django.conf import settings
from django.core.cache import cache
from django.shortcuts import render
from django.utils.cache import patch_cache_control
from django.utils.deprecation import MiddlewareMixin
from kombu.exceptions import OperationalError
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class AuthenticationProtectionMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if not request.path.startswith("/accounts/"):
            return None
        if request.path.startswith("/accounts/google/") and not settings.GOOGLE_LOGIN_ENABLED:
            return render(request, "customers/google_unavailable.html", status=503)
        if request.method == "POST":
            ip = get_client_ip(request) or "unknown"
            key = "auth-post:" + hashlib.sha256(ip.encode()).hexdigest()
            try:
                # django-redis implements add (SET NX) and incr atomically.
                if cache.add(key, 1, timeout=60):
                    count = 1
                else:
                    try:
                        count = cache.incr(key)
                    except ValueError:  # Counter expired between add and incr.
                        cache.add(key, 1, timeout=60)
                        count = 1
            except RedisError:
                return self.unavailable(request)
            if count > 20:
                response = render(request, "429.html", status=429)
                response["Retry-After"] = "60"
                return response

    def process_exception(self, request, exception):
        if request.path.startswith("/accounts/") and isinstance(exception, (RedisError, OperationalError)):
            return self.unavailable(request)

    @staticmethod
    def unavailable(request):
        logger.error("Authentication dependency unavailable")
        response = render(request, "customers/unavailable.html", status=503)
        response["Retry-After"] = "60"
        return response

    def process_response(self, request, response):
        if request.path.startswith(("/accounts/", "/manage-profile/")):
            patch_cache_control(response, no_store=True, private=True)
            response["Referrer-Policy"] = "same-origin"
            # Account forms can be shown in our own storefront popup only.
            response["X-Frame-Options"] = "SAMEORIGIN"
            response["Content-Security-Policy"] = "frame-ancestors 'self'"
        return response
