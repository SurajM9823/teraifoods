import json
import smtplib
import logging

from celery import shared_task
from cryptography.fernet import InvalidToken
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection

from .email_backend import mail_cipher

logger = logging.getLogger("customers.email")


@shared_task(bind=True, ignore_result=True, max_retries=3, soft_time_limit=25, time_limit=30)
def deliver_email(self, encrypted):
    logger.info("email_delivery_started task_id=%s attempt=%s", self.request.id, self.request.retries + 1)
    try:
        payload = json.loads(mail_cipher().decrypt(encrypted.encode(), ttl=300))
    except InvalidToken:
        logger.warning("email_discarded task_id=%s reason=expired_or_wrong_encryption_key", self.request.id)
        return  # Never deliver stale OTPs or messages encrypted with an old key.
    alternatives = payload.pop("alternatives", [])
    message = EmailMultiAlternatives(
        **payload, connection=get_connection(settings.EMAIL_DELIVERY_BACKEND)
    )
    for content, mimetype in alternatives:
        message.attach_alternative(content, mimetype)
    try:
        sent = message.send(fail_silently=False)
        if sent != 1:
            raise smtplib.SMTPException("Message was not accepted")
        logger.info("email_smtp_accepted task_id=%s", self.request.id)
    except (OSError, smtplib.SMTPException) as exc:
        status = "email_delivery_failed" if self.request.retries >= self.max_retries else "email_delivery_retry"
        code = getattr(exc, "smtp_code", None)
        logger.error("%s task_id=%s error_type=%s smtp_code=%s", status,
                     self.request.id, type(exc).__name__, code if isinstance(code, int) else "unavailable")
        # SMTP exceptions can contain recipient information: do not log them.
        raise self.retry(exc=RuntimeError("Email delivery temporarily unavailable"),
                         countdown=min(15 * 2 ** self.request.retries, 60)) from None
