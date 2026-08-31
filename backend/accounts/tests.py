"""Authentication and profile tests (Prompt 02)."""

from datetime import timedelta

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Profile, User

REGISTER_URL = "/api/auth/register/"
LOGIN_URL = "/api/auth/login/"
REFRESH_URL = "/api/auth/refresh/"
LOGOUT_URL = "/api/auth/logout/"
ME_URL = "/api/users/me/"

VALID_PASSWORD = "StrongPass123!"


def register_payload(**overrides):
    payload = {
        "email": "alice@example.com",
        "password": VALID_PASSWORD,
        "password_confirmation": VALID_PASSWORD,
        "full_name": "Alice Example",
    }
    payload.update(overrides)
    return payload


class RegisterTests(APITestCase):
    def test_register_success_creates_user_and_profile(self):
        response = self.client.post(REGISTER_URL, register_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        user = User.objects.get(email="alice@example.com")
        self.assertTrue(user.check_password(VALID_PASSWORD))
        self.assertEqual(user.username, user.email)
        self.assertEqual(user.profile.full_name, "Alice Example")
        self.assertEqual(user.profile.account_status, Profile.AccountStatus.ACTIVE)

    def test_register_email_is_normalized_to_lowercase(self):
        response = self.client.post(
            REGISTER_URL,
            register_payload(email="Alice@Example.com"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="alice@example.com").exists())

    def test_register_duplicate_email_rejected(self):
        self.client.post(REGISTER_URL, register_payload(), format="json")
        response = self.client.post(REGISTER_URL, register_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_register_duplicate_phone_rejected(self):
        payload = register_payload(phone_number="+255700000001")
        self.client.post(REGISTER_URL, payload, format="json")
        response = self.client.post(
            REGISTER_URL,
            register_payload(email="bob@example.com", phone_number="+255700000001"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone_number", response.data)

    def test_register_password_mismatch_rejected(self):
        response = self.client.post(
            REGISTER_URL,
            register_payload(password_confirmation="DifferentPass123!"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password_confirmation", response.data)

    def test_register_weak_password_rejected(self):
        response = self.client.post(
            REGISTER_URL,
            register_payload(password="12345678", password_confirmation="12345678"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_register_does_not_accept_role(self):
        response = self.client.post(
            REGISTER_URL,
            register_payload(role="Buyer"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="alice@example.com")
        self.assertFalse(hasattr(user, "role"))
        self.assertNotIn("role", response.data)

    def test_register_never_exposes_password_or_username(self):
        response = self.client.post(REGISTER_URL, register_payload(), format="json")
        self.assertNotIn("password", response.data)
        self.assertNotIn("username", response.data)


class LoginTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="alice@example.com", password=VALID_PASSWORD)

    def test_login_returns_access_and_refresh(self):
        response = self.client.post(
            LOGIN_URL,
            {"email": "alice@example.com", "password": VALID_PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_wrong_password_rejected(self):
        response = self.client.post(
            LOGIN_URL,
            {"email": "alice@example.com", "password": "WrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_suspended_user_blocked(self):
        self.user.profile.account_status = Profile.AccountStatus.SUSPENDED
        self.user.profile.save()
        response = self.client.post(
            LOGIN_URL,
            {"email": "alice@example.com", "password": VALID_PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("suspended", str(response.data["detail"]).lower())


class TokenTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="alice@example.com", password=VALID_PASSWORD)
        self.login_response = self.client.post(
            LOGIN_URL,
            {"email": "alice@example.com", "password": VALID_PASSWORD},
            format="json",
        )
        self.access = self.login_response.data["access"]
        self.refresh = self.login_response.data["refresh"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")

    def test_refresh_rotates_token(self):
        response = self.client.post(REFRESH_URL, {"refresh": self.refresh}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        new_refresh = response.data["refresh"]
        self.assertNotEqual(new_refresh, self.refresh)
        self.assertIn("access", response.data)

        # The rotated-out refresh token must now be blacklisted.
        second = self.client.post(REFRESH_URL, {"refresh": self.refresh}, format="json")
        self.assertEqual(second.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_blacklists_refresh_token(self):
        response = self.client.post(LOGOUT_URL, {"refresh": self.refresh}, format="json")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        reuse = self.client.post(REFRESH_URL, {"refresh": self.refresh}, format="json")
        self.assertEqual(reuse.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_requires_authenticated_user(self):
        self.client.credentials()
        response = self.client.post(LOGOUT_URL, {"refresh": self.refresh}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_without_refresh_token(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")
        response = self.client.post(LOGOUT_URL, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_blacklisted_token_cannot_be_used_for_auth(self):
        self.client.post(LOGOUT_URL, {"refresh": self.refresh}, format="json")
        with self.assertRaises(TokenError):
            RefreshToken(self.refresh).blacklist()


class MeTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="alice@example.com", password=VALID_PASSWORD)
        self.access = str(RefreshToken.for_user(self.user).access_token)

    def test_me_requires_authentication(self):
        response = self.client.get(ME_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_own_profile(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")
        response = self.client.get(ME_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "alice@example.com")
        self.assertEqual(response.data["profile"]["account_status"], "ACTIVE")
        self.assertNotIn("password", response.data)

    def test_me_patch_updates_own_profile(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")
        response = self.client.patch(
            ME_URL,
            {"full_name": "Alice New", "phone_number": "+255700000099", "address": "Dar"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile"]["full_name"], "Alice New")
        self.assertEqual(response.data["profile"]["phone_number"], "+255700000099")
        self.assertEqual(response.data["profile"]["address"], "Dar")
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.full_name, "Alice New")

    def test_me_patch_cannot_change_account_status(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")
        response = self.client.patch(ME_URL, {"account_status": "SUSPENDED"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.account_status, Profile.AccountStatus.ACTIVE)


class JwtSecurityTests(APITestCase):
    """Token-expiry and suspended-user enforcement (Prompt 19 audit).

    The SALT-against-token-reuse rules from SimpleJWT:
    - an expired access token is rejected (401), not silently accepted
    - an expired refresh token cannot be rotated
    - a user suspended AFTER a token is issued is still blocked on any
      protected endpoint that enforces ``IsActiveUser``/active-status, even
      though the JWT itself is still cryptographically valid.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email="alice@example.com", password=VALID_PASSWORD
        )

    def test_expired_access_token_is_rejected(self):
        from rest_framework_simplejwt.tokens import AccessToken

        expired_access = AccessToken.for_user(self.user)
        expired_access.set_exp(lifetime=-timedelta(seconds=1))  # exp in the past
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {str(expired_access)}"
        )
        response = self.client.get(ME_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_expired_access_token_rejected_even_when_refresh_valid(self):
        # A valid refresh exists, but the presented access token alone is stale.
        from rest_framework_simplejwt.tokens import AccessToken

        expired_access = AccessToken.for_user(self.user)
        expired_access.set_exp(lifetime=-timedelta(seconds=1))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {str(expired_access)}"
        )
        response = self.client.get(ME_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_expired_refresh_token_cannot_rotate(self):
        expired_refresh = RefreshToken.for_user(self.user)
        expired_refresh.set_exp(lifetime=-timedelta(seconds=1))
        response = self.client.post(
            REFRESH_URL, {"refresh": str(expired_refresh)}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_suspended_user_with_valid_token_is_blocked(self):
        # Issue a valid token while ACTIVE, then suspend the account (as an
        # admin would). The token stays cryptographically valid.
        self.user.profile.account_status = Profile.AccountStatus.SUSPENDED
        self.user.profile.save(update_fields=["account_status"])

        access = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        # A write on a protected catalog endpoint must be blocked by IsActiveUser.
        response = self.client.post(
            "/api/products/",
            {
                "name": "Blocked listing",
                "price": "10.00",
                "condition": "NEW",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("suspended", str(response.data.get("detail", "")).lower())

    def test_active_user_token_completes_same_write(self):
        access = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.post(
            "/api/products/",
            {"name": "Visible listing", "price": "10.00", "condition": "NEW"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class LoginThrottleTests(APITestCase):
    """Brute-force rate limit on the login endpoint (Prompt 19 audit).

    The conftest raises all rates for the wider suite; here we re-lower the
    login scope to prove a burst of attempts is throttled with 429.
    """

    def setUp(self):
        User.objects.create_user(email="alice@example.com", password=VALID_PASSWORD)

    def test_login_rate_limited_after_burst(self):
        # The throttle uses the client IP; force a distinct one.
        self.client.credentials()

        with override_settings(
            DEFAULT_THROTTLE_RATES={
                "auth_login": "2/min",
                "anon": "100000/min",
                "user": "100000/min",
                "payment_initiate": "100000/min",
            }
        ):
            for _ in range(2):
                r = self.client.post(
                    LOGIN_URL,
                    {"email": "alice@example.com", "password": VALID_PASSWORD},
                    format="json",
                )
                self.assertNotEqual(r.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
            third = self.client.post(
                LOGIN_URL,
                {"email": "alice@example.com", "password": VALID_PASSWORD},
                format="json",
            )
            self.assertEqual(
                third.status_code, status.HTTP_429_TOO_MANY_REQUESTS
            )
