"""Queue encrypted messages; never place plaintext OTPs in broker task arguments."""
import base64
import hashlib
import hmac
import json

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


def mail_cipher():
    key = hmac.new(settings.SECRET_KEY.encode(), b"terai-email-queue-v1", hashlib.sha256).digest()
    return Fernet(base64.urlsafe_b64encode(key))


class QueuedEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        from .tasks import deliver_email

        count = 0
        for message in email_messages or []:
            if message.attachments:
                raise ValueError("Account emails must not contain attachments")
            payload = {"subject": message.subject, "body": message.body,
                       "from_email": message.from_email, "to": message.to,
                       "alternatives": list(getattr(message, "alternatives", []))}
            encrypted = mail_cipher().encrypt(json.dumps(payload).encode()).decode()
            deliver_email.apply_async(args=[encrypted], expires=300,
                                      argsrepr="[<encrypted account email>]")
            count += 1
        return count
