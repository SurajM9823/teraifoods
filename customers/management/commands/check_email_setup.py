"""Inspect loaded configuration and test dependencies without revealing credentials."""
import smtplib

from django.conf import settings
from django.core.cache import cache
from django.core.mail import get_connection
from django.core.management.base import BaseCommand, CommandError

from config.celery import app


class Command(BaseCommand):
    help = "Show safe email configuration; optionally test SMTP login (does not send email)."

    def add_arguments(self, parser):
        parser.add_argument("--smtp", action="store_true", help="Connect, negotiate TLS and authenticate; send no mail")

    def handle(self, *args, **options):
        for name in ("SETTINGS_MODULE", "EMAIL_BACKEND", "EMAIL_DELIVERY_BACKEND", "EMAIL_HOST", "EMAIL_PORT", "EMAIL_USE_TLS", "EMAIL_USE_SSL"):
            self.stdout.write(f"{name}={getattr(settings, name, '')}")
        for name in ("EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD", "DEFAULT_FROM_EMAIL"):
            self.stdout.write(f"{name}={'set' if getattr(settings, name, '') else 'MISSING'}")
        failures = []
        try:
            cache.get("email-diagnostics-connectivity")
            self.stdout.write("Cache: reachable")
        except Exception as exc:
            failures.append(f"Cache: {type(exc).__name__}")
        try:
            with app.connection_for_write() as connection:
                connection.ensure_connection(max_retries=0)
            self.stdout.write("Celery broker: reachable")
            workers = app.control.ping(timeout=3)
            if workers:
                self.stdout.write(f"Celery workers responding: {len(workers)}")
            else:
                failures.append("No Celery worker answered within 3 seconds; check its service, environment and broker")
        except Exception as exc:
            failures.append(f"Celery broker/worker check: {type(exc).__name__}")
        if options["smtp"]:
            try:
                with get_connection(settings.EMAIL_DELIVERY_BACKEND) as connection:
                    self.stdout.write("SMTP connection/authentication: OK (no email sent)")
            except (OSError, smtplib.SMTPException, ValueError) as exc:
                code = getattr(exc, "smtp_code", None)
                failures.append(f"SMTP: {type(exc).__name__}, code={code if isinstance(code, int) else 'unavailable'}")
        if failures:
            raise CommandError("; ".join(failures))
