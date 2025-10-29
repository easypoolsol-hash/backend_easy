"""
Firebase Authentication Tests

Tests Firebase token verification and user auto-creation.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
import pytest
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory

from bus_kiosk_backend.core.authentication import FirebaseAuthentication

User = get_user_model()


@pytest.mark.django_db
class TestFirebaseAuthentication:
    """Test Firebase authentication and user auto-creation"""

    def test_no_auth_header_returns_none(self):
        """No Authorization header → returns None (let other auth handle)"""
        factory = APIRequestFactory()
        request = factory.get("/api/v1/users/me/")

        auth = FirebaseAuthentication()
        result = auth.authenticate(request)

        assert result is None

    def test_non_bearer_token_returns_none(self):
        """Non-Bearer token → returns None (let other auth handle)"""
        factory = APIRequestFactory()
        request = factory.get("/api/v1/users/me/", HTTP_AUTHORIZATION="Basic sometoken")

        auth = FirebaseAuthentication()
        result = auth.authenticate(request)

        assert result is None

    @patch("bus_kiosk_backend.core.authentication.auth.verify_id_token")
    def test_valid_token_creates_new_user(self, mock_verify):
        """Valid Firebase token → creates Django user on first login"""
        mock_verify.return_value = {"uid": "firebase_uid_123", "email": "newadmin@school.com", "name": "John Doe"}

        factory = APIRequestFactory()
        request = factory.get("/api/v1/users/me/", HTTP_AUTHORIZATION="Bearer valid_firebase_token")

        # Verify user doesn't exist yet
        assert not User.objects.filter(username="firebase_uid_123").exists()

        auth = FirebaseAuthentication()
        user, _ = auth.authenticate(request)

        # User was created
        assert user is not None
        assert user.username == "firebase_uid_123"
        assert user.email == "newadmin@school.com"
        assert user.is_active is True
        assert user.is_staff is False
        assert user.groups.count() == 0  # No role assigned yet

    @patch("bus_kiosk_backend.core.authentication.auth.verify_id_token")
    def test_valid_token_returns_existing_user(self, mock_verify):
        """Valid Firebase token → returns existing Django user"""
        # Create user first
        user = User.objects.create(username="firebase_uid_456", email="existing@school.com")

        mock_verify.return_value = {"uid": "firebase_uid_456", "email": "existing@school.com", "name": "Jane Smith"}

        factory = APIRequestFactory()
        request = factory.get("/api/v1/users/me/", HTTP_AUTHORIZATION="Bearer valid_firebase_token")

        auth = FirebaseAuthentication()
        authenticated_user, _ = auth.authenticate(request)

        assert authenticated_user.user_id == user.user_id
        assert User.objects.filter(username="firebase_uid_456").count() == 1

    @patch("bus_kiosk_backend.core.authentication.auth.verify_id_token")
    def test_updates_email_if_changed(self, mock_verify):
        """Email changed in Firebase → updates Django user"""
        user = User.objects.create(username="firebase_uid_789", email="old@school.com")

        mock_verify.return_value = {"uid": "firebase_uid_789", "email": "new@school.com", "name": "Admin User"}

        factory = APIRequestFactory()
        request = factory.get("/api/v1/users/me/", HTTP_AUTHORIZATION="Bearer valid_firebase_token")

        auth = FirebaseAuthentication()
        _, _ = auth.authenticate(request)

        user.refresh_from_db()
        assert user.email == "new@school.com"

    @patch("bus_kiosk_backend.core.authentication.auth.verify_id_token")
    def test_handles_missing_name(self, mock_verify):
        """Firebase token without name → creates user with empty name"""
        mock_verify.return_value = {"uid": "firebase_uid_noname", "email": "noname@school.com"}

        factory = APIRequestFactory()
        request = factory.get("/api/v1/users/me/", HTTP_AUTHORIZATION="Bearer valid_firebase_token")

        auth = FirebaseAuthentication()
        user, _ = auth.authenticate(request)

        assert user.username == "firebase_uid_noname"
        assert user.first_name == ""
        assert user.last_name == ""

    @patch("bus_kiosk_backend.core.authentication.auth.verify_id_token")
    def test_expired_token_raises_error(self, mock_verify):
        """Expired Firebase token → raises AuthenticationFailed"""
        from firebase_admin import auth as firebase_auth

        mock_verify.side_effect = firebase_auth.ExpiredIdTokenError("Token expired", cause=None)

        factory = APIRequestFactory()
        request = factory.get("/api/v1/users/me/", HTTP_AUTHORIZATION="Bearer expired_token")

        auth = FirebaseAuthentication()

        with pytest.raises(AuthenticationFailed) as exc:
            auth.authenticate(request)

        assert "expired" in str(exc.value).lower()

    @patch("bus_kiosk_backend.core.authentication.auth.verify_id_token")
    def test_revoked_token_raises_error(self, mock_verify):
        """Revoked Firebase token → raises AuthenticationFailed"""
        from firebase_admin import auth as firebase_auth

        mock_verify.side_effect = firebase_auth.RevokedIdTokenError("Token revoked")

        factory = APIRequestFactory()
        request = factory.get("/api/v1/users/me/", HTTP_AUTHORIZATION="Bearer revoked_token")

        auth = FirebaseAuthentication()

        with pytest.raises(AuthenticationFailed) as exc:
            auth.authenticate(request)

        assert "revoked" in str(exc.value).lower()

    @patch("bus_kiosk_backend.core.authentication.auth.verify_id_token")
    def test_invalid_token_raises_error(self, mock_verify):
        """Invalid Firebase token → raises AuthenticationFailed"""
        from firebase_admin import auth as firebase_auth

        mock_verify.side_effect = firebase_auth.InvalidIdTokenError("Invalid token")

        factory = APIRequestFactory()
        request = factory.get("/api/v1/users/me/", HTTP_AUTHORIZATION="Bearer invalid_token")

        auth = FirebaseAuthentication()

        with pytest.raises(AuthenticationFailed) as exc:
            auth.authenticate(request)

        assert "invalid" in str(exc.value).lower()

    @patch("bus_kiosk_backend.core.authentication.auth.verify_id_token")
    def test_user_has_no_permissions_by_default(self, mock_verify):
        """Auto-created user has no permissions (secure by default)"""
        mock_verify.return_value = {"uid": "firebase_uid_noperms", "email": "noperms@school.com", "name": "No Perms User"}

        factory = APIRequestFactory()
        request = factory.get("/api/v1/users/me/", HTTP_AUTHORIZATION="Bearer valid_firebase_token")

        auth = FirebaseAuthentication()
        user, _ = auth.authenticate(request)

        # Secure by default
        assert user.is_staff is False
        assert user.is_superuser is False
        assert user.groups.count() == 0
        assert user.is_active is True  # Can login but has no permissions
