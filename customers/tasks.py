import json
import smtplib

from celery import shared_task
from cryptography.fernet import InvalidToken
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection

from .email_backend import mail_cipher


@shared_task(bind=True, ignore_result=True, max_retries=3, soft_time_limit=25, time_limit=30)
def deliver_email(self, encrypted):
    try:
        payload = json.loads(mail_cipher().decrypt(encrypted.encode(), ttl=300))
    except InvalidToken:
        return  # Never deliver stale OTPs or messages encrypted with an old key.
    alternatives = payload.pop("alternatives", [])
    message = EmailMultiAlternatives(
        **payload, connection=get_connection(settings.EMAIL_DELIVERY_BACKEND)
    )
    for content, mimetype in alternatives:
        message.attach_alternative(content, mimetype)
    try:
        message.send(fail_silently=False)
    except (OSError, smtplib.SMTPException):
        # SMTP exceptions can contain recipient information: do not log them.
        raise self.retry(exc=RuntimeError("Email delivery temporarily unavailable"),
                         countdown=min(15 * 2 ** self.request.retries, 60)) from None
