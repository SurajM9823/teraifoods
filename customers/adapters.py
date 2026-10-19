from allauth.account.models import EmailAddress
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def can_authenticate_by_email(self, login, email):
        """Only Google-authoritative addresses can match a verified customer."""
        if login.account.provider != "google":
            return False
        data = login.account.extra_data
        verified = data.get("email_verified", data.get("verified_email")) is True
        domain = email.rsplit("@", 1)[-1].lower()
        authoritative = domain in {"gmail.com", "googlemail.com"} or bool(data.get("hd"))
        return verified and authoritative and EmailAddress.objects.filter(
            email=email.lower(), verified=True, user__is_active=True,
            user__is_staff=False, user__is_superuser=False,
        ).exists()
