import re
import smtplib
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from redis.exceptions import ConnectionError as RedisConnectionError

from .adapters import SocialAccountAdapter
from .email_backend import QueuedEmailBackend, mail_cipher
from .tasks import deliver_email

TEST_SETTINGS = dict(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_DELIVERY_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    ALLAUTH_TRUSTED_PROXY_COUNT=0,
)
PASSWORD = "Orchard!river72-willow"


@override_settings(**TEST_SETTINGS)
class CustomerAuthenticationTests(TestCase):
    def setUp(self):
        cache.clear()

    def verified_user(self, email="shopper@example.com"):
        user = get_user_model().objects.create_user(username=email, email=email, password=PASSWORD)
        EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
        return user

    def signup(self, email="new@example.com"):
        return self.client.post(reverse("account_signup"), {
            "email": email, "password1": PASSWORD, "password2": PASSWORD,
        })

    def code(self):
        for message in reversed(mail.outbox):
            match = re.search(r"\b\d{6}\b", message.body)
            if match:
                self.assertNotIn(PASSWORD, message.body)
                return match.group()
        self.fail("No six-digit OTP was emailed")

    def test_signup_requires_real_otp_and_replay_is_rejected(self):
        response = self.signup()
        self.assertRedirects(response, reverse("account_email_verification_sent"))
        self.assertNotIn("_auth_user_id", self.client.session)
        user = get_user_model().objects.get(email="new@example.com")
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))
        code = self.code()
        page = self.client.get(reverse("account_email_verification_sent"))
        self.assertNotContains(page, code)
        response = self.client.post(reverse("account_email_verification_sent"), {"code": code})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(EmailAddress.objects.get(user=user).verified)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertContains(self.client.get("/manage-profile/"), user.email)
        other = Client()
        other.post(reverse("account_email_verification_sent"), {"code": code})
        self.assertNotIn("_auth_user_id", other.session)

    def test_wrong_code_exhausts_attempts(self):
        self.signup()
        code = self.code()
        for _ in range(3):
            self.client.post(reverse("account_email_verification_sent"), {"code": "invalid"})
        self.client.post(reverse("account_email_verification_sent"), {"code": code})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertFalse(EmailAddress.objects.get(email="new@example.com").verified)

    def test_expired_code_is_rejected(self):
        self.signup()
        code = self.code()
        session = self.client.session
        state = session["account_email_verification_code"]
        state["at"] -= 601
        session["account_email_verification_code"] = state
        session.save()
        self.client.post(reverse("account_email_verification_sent"), {"code": code})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_duplicate_signup_does_not_create_another_account(self):
        self.verified_user()
        response = self.signup("SHOPPER@example.com")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_password_login_case_insensitive_and_redirect_safe(self):
        self.verified_user()
        response = self.client.post(reverse("account_login"), {
            "login": "SHOPPER@EXAMPLE.COM", "password": PASSWORD, "next": "https://evil.example/",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/manage-profile/")
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_by_email_code(self):
        self.verified_user()
        response = self.client.post(reverse("account_request_login_code"), {"email": "shopper@example.com"})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.client.post(reverse("account_confirm_login_code"), {"code": self.code()})
        self.assertIn("_auth_user_id", self.client.session)

    def test_password_recovery_revokes_old_sessions(self):
        user = self.verified_user()
        old_session = Client()
        old_session.force_login(user)
        response = self.client.post(reverse("account_reset_password"), {"email": user.email})
        self.assertEqual(response.status_code, 302)
        self.client.post(reverse("account_confirm_password_reset_code"), {"code": self.code()})
        new_password = "NewOrchard!river43-cedar"
        response = self.client.post(reverse("account_complete_password_reset"), {
            "password1": new_password, "password2": new_password,
        })
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertTrue(user.check_password(new_password))
        self.assertFalse(user.check_password(PASSWORD))
        self.assertEqual(old_session.get("/manage-profile/").status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_unknown_reset_is_generic_and_does_not_send_mail(self):
        response = self.client.post(reverse("account_reset_password"), {"email": "unknown@example.com"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(response.url, reverse("account_confirm_password_reset_code"))

    def test_injection_wrong_password_and_weak_password_do_not_authenticate(self):
        self.verified_user()
        for login in ["' OR 1=1 --", "shopper@example.com"]:
            self.client.post(reverse("account_login"), {"login": login, "password": "incorrect"})
            self.assertNotIn("_auth_user_id", self.client.session)
        self.client.post(reverse("account_signup"), {"email": "weak@example.com", "password1": "1234", "password2": "1234"})
        self.assertFalse(get_user_model().objects.filter(email="weak@example.com").exists())

    def test_rate_limit_and_cache_failure_fail_closed(self):
        self.verified_user()
        responses = [self.client.post(reverse("account_login"), {
            "login": "shopper@example.com", "password": "wrong",
        }).status_code for _ in range(12)]
        self.assertIn(429, responses)
        self.assertNotIn("_auth_user_id", self.client.session)
        with patch("customers.middleware.cache.add", side_effect=RedisConnectionError):
            self.assertEqual(self.client.post(reverse("account_login"), {}).status_code, 503)

    def test_csrf_required_and_get_logout_does_not_log_out(self):
        secure = Client(enforce_csrf_checks=True)
        self.assertEqual(secure.post(reverse("account_signup"), {}).status_code, 403)
        user = self.verified_user()
        secure.force_login(user)
        self.assertEqual(secure.post(reverse("account_logout"), {}).status_code, 403)
        secure.get(reverse("account_logout"))
        self.assertIn("_auth_user_id", secure.session)

    def test_profile_requires_verified_session_and_is_not_cached(self):
        self.assertEqual(self.client.get("/manage-profile/").status_code, 302)
        user = self.verified_user()
        self.client.force_login(user)
        response = self.client.get("/manage-profile/")
        self.assertContains(response, user.email)
        self.assertIn("no-store", response["Cache-Control"])

    def test_email_queue_payload_encrypted_and_worker_delivers(self):
        message = mail.EmailMultiAlternatives("OTP", "Code 987654", "sender@example.com", ["recipient@example.com"])
        with patch("customers.tasks.deliver_email.apply_async") as enqueue:
            self.assertEqual(QueuedEmailBackend().send_messages([message]), 1)
        payload = enqueue.call_args.kwargs["args"][0]
        self.assertNotIn("987654", payload)
        self.assertIn(b"987654", mail_cipher().decrypt(payload.encode()))
        deliver_email.run(payload)
        self.assertEqual(mail.outbox[-1].body, "Code 987654")

    def test_smtp_failure_logs_reason_without_credentials_or_otp(self):
        message = mail.EmailMultiAlternatives("OTP", "Code 987654", "sender@example.com", ["recipient@example.com"])
        with patch("customers.tasks.deliver_email.apply_async") as enqueue:
            QueuedEmailBackend().send_messages([message])
        payload = enqueue.call_args.kwargs["args"][0]
        error = smtplib.SMTPAuthenticationError(535, b"secret-app-password 987654 recipient@example.com")
        with patch("customers.tasks.EmailMultiAlternatives.send", side_effect=error), patch.object(deliver_email, "retry", side_effect=RuntimeError("retry")), self.assertLogs("customers.email", level="INFO") as logs:
            with self.assertRaises(RuntimeError):
                deliver_email.run(payload)
        output = "\n".join(logs.output)
        self.assertIn("SMTPAuthenticationError", output)
        self.assertIn("smtp_code=535", output)
        for private_value in ("secret-app-password", "987654", "recipient@example.com"):
            self.assertNotIn(private_value, output)

    def test_google_email_matching_requires_verified_customer_and_authoritative_google(self):
        user = self.verified_user("customer@gmail.com")
        login = SimpleNamespace(account=SimpleNamespace(provider="google", extra_data={"email_verified": True}))
        adapter = SocialAccountAdapter()
        self.assertTrue(adapter.can_authenticate_by_email(login, user.email))
        user.is_staff = True
        user.save()
        self.assertFalse(adapter.can_authenticate_by_email(login, user.email))
        login.account.extra_data["email_verified"] = False
        self.assertFalse(adapter.can_authenticate_by_email(login, user.email))


GOOGLE = {"google": {"APP": {"client_id": "test.apps.googleusercontent.com", "secret": "test-secret", "key": ""}, "SCOPE": ["email", "profile"], "OAUTH_PKCE_ENABLED": True}}


@override_settings(**TEST_SETTINGS, GOOGLE_LOGIN_ENABLED=True, SOCIALACCOUNT_PROVIDERS=GOOGLE)
class GoogleFlowTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_oauth_start_pkce_callback_and_replay(self):
        start = self.client.post("/accounts/google/login/", {"process": "login"})
        self.assertEqual(start.status_code, 302)
        query = parse_qs(urlsplit(start.url).query)
        self.assertEqual(query["code_challenge_method"], ["S256"])
        state = query["state"][0]
        claims = {"sub": "test-google-user", "email": "google-shopper@gmail.com", "email_verified": True, "given_name": "Shopper"}
        with patch("allauth.socialaccount.providers.oauth2.client.OAuth2Client.get_access_token", return_value={"access_token": "test-token", "id_token": "test-id-token"}), patch("allauth.socialaccount.providers.google.views._verify_and_decode", return_value=claims):
            response = self.client.get("/accounts/google/login/callback/", {"state": state, "code": "test-code"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertTrue(SocialAccount.objects.filter(provider="google", uid="test-google-user").exists())
        self.client.post(reverse("account_logout"))
        self.client.get("/accounts/google/login/callback/", {"state": state, "code": "test-code"})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_google_rejects_missing_state_without_contacting_provider(self):
        with patch("allauth.socialaccount.providers.oauth2.client.OAuth2Client.get_access_token") as token:
            self.client.get("/accounts/google/login/callback/", {"code": "fake"})
            token.assert_not_called()
        self.assertNotIn("_auth_user_id", self.client.session)
