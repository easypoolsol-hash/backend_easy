"""
Test Firebase Authentication for Kiosk Auto-Creation

Tests that kiosks are automatically created when Firebase users with
custom claims authenticate via the backend API.
"""

from unittest.mock import patch

from django.test import RequestFactory
import pytest
from rest_framework.test import APIClient

from bus_kiosk_backend.core.authentication import FirebaseAuthentication
from kiosks.models import Kiosk


@pytest.mark.django_db
class TestFirebaseKioskAuthentication:
    """Test Firebase authentication with kiosk custom claims"""

    def setup_method(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()
        self.auth = FirebaseAuthentication()
        self.client = APIClient()

    @patch("bus_kiosk_backend.core.authentication.auth.verify_id_token")
    def test_kiosk_auto_created_on_first_api_call(self, mock_verify):
        """
        Test that kiosk is automatically created when Firebase user with
        kiosk custom claims makes first API request
        """
        # Mock Firebase token with kiosk custom claims
        mock_verify.return_value = {"uid": "firebase_test_uid_001", "email": "kiosk001@easypool.in", "type": "kiosk", "kiosk_id": "TEST_KIOSK_001"}

        # Create request with Firebase token
        request = self.factory.get("/api/kiosks/heartbeat/")
        request.META["HTTP_AUTHORIZATION"] = "Bearer fake_firebase_token"

        # Authenticate
        result = self.auth.authenticate(request)

        # Should return kiosk object
        assert result is not None
        kiosk, auth_token = result
        assert auth_token is None

        # Verify kiosk was created
        assert isinstance(kiosk, Kiosk)
        assert kiosk.kiosk_id == "TEST_KIOSK_001"
        assert kiosk.firebase_uid == "firebase_test_uid_001"
        assert kiosk.is_active is False  # CRITICAL: Must be inactive
        assert kiosk.is_authenticated is True

        # Verify it's in database
        db_kiosk = Kiosk.objects.get(kiosk_id="TEST_KIOSK_001")
        assert db_kiosk.firebase_uid == "firebase_test_uid_001"
        assert db_kiosk.is_active is False

    @patch("bus_kiosk_backend.core.authentication.auth.verify_id_token")
    def test_kiosk_not_created_twice(self, mock_verify):
        """Test that existing kiosk is returned, not created again"""
        # Create kiosk first
        Kiosk.objects.create(kiosk_id="TEST_KIOSK_002", firebase_uid="firebase_test_uid_002", is_active=False)

        # Mock Firebase token
        mock_verify.return_value = {"uid": "firebase_test_uid_002", "email": "kiosk002@easypool.in", "type": "kiosk", "kiosk_id": "TEST_KIOSK_002"}

        # Make request
        request = self.factory.get("/api/kiosks/heartbeat/")
        request.META["HTTP_AUTHORIZATION"] = "Bearer fake_firebase_token"

        # Authenticate
        result = self.auth.authenticate(request)
        kiosk, _ = result

        # Should return existing kiosk
        assert kiosk.kiosk_id == "TEST_KIOSK_002"
        assert kiosk.firebase_uid == "firebase_test_uid_002"

        # Verify only one kiosk exists
        assert Kiosk.objects.filter(kiosk_id="TEST_KIOSK_002").count() == 1

    @patch("bus_kiosk_backend.core.authentication.auth.verify_id_token")
    def test_kiosk_created_inactive_by_default(self, mock_verify):
        """Test that auto-created kiosks start in inactive state"""
        mock_verify.return_value = {"uid": "firebase_test_uid_003", "email": "kiosk003@easypool.in", "type": "kiosk", "kiosk_id": "TEST_KIOSK_003"}

        request = self.factory.get("/api/kiosks/heartbeat/")
        request.META["HTTP_AUTHORIZATION"] = "Bearer fake_firebase_token"

        result = self.auth.authenticate(request)
        kiosk, _ = result

        # CRITICAL TEST: Kiosk must be inactive
        assert kiosk.is_active is False, "Kiosk should be inactive by default!"

        # Double-check in database
        db_kiosk = Kiosk.objects.get(kiosk_id="TEST_KIOSK_003")
        assert db_kiosk.is_active is False, "Kiosk should be inactive in database!"

    @patch("bus_kiosk_backend.core.authentication.auth.verify_id_token")
    def test_regular_user_not_created_as_kiosk(self, mock_verify):
        """Test that Firebase users without kiosk claims create User, not Kiosk"""
        # Mock Firebase token WITHOUT kiosk custom claims
        mock_verify.return_value = {
            "uid": "firebase_regular_user",
            "email": "regular@easypool.in",
            "name": "Regular User",
            # NO 'type' or 'kiosk_id' claims
        }

        request = self.factory.get("/api/students/")
        request.META["HTTP_AUTHORIZATION"] = "Bearer fake_firebase_token"

        result = self.auth.authenticate(request)
        user, _ = result

        # Should create User, not Kiosk
        from django.contrib.auth import get_user_model

        User = get_user_model()
        assert isinstance(user, User)
        assert not isinstance(user, Kiosk)

        # Verify no kiosk was created
        assert Kiosk.objects.count() == 0

    @patch("bus_kiosk_backend.core.authentication.auth.verify_id_token")
    def test_missing_kiosk_id_in_claims(self, mock_verify):
        """Test that kiosk with missing kiosk_id is not created"""
        # Mock Firebase token with type but no kiosk_id
        mock_verify.return_value = {
            "uid": "firebase_incomplete",
            "email": "incomplete@easypool.in",
            "type": "kiosk",
            # MISSING: 'kiosk_id'
        }

        request = self.factory.get("/api/kiosks/heartbeat/")
        request.META["HTTP_AUTHORIZATION"] = "Bearer fake_firebase_token"

        result = self.auth.authenticate(request)
        user, _ = result

        # Should create regular User, not Kiosk
        from django.contrib.auth import get_user_model

        User = get_user_model()
        assert isinstance(user, User)

        # Verify no kiosk was created
        assert Kiosk.objects.count() == 0

    @patch("bus_kiosk_backend.core.authentication.auth.verify_id_token")
    def test_kiosk_id_stored_correctly(self, mock_verify):
        """Test that kiosk_id from custom claims is stored correctly"""
        mock_verify.return_value = {
            "uid": "firebase_test_uid_004",
            "email": "kiosk004@easypool.in",
            "type": "kiosk",
            "kiosk_id": "BUS_ALPHA_KIOSK_001",  # Different format
        }

        request = self.factory.get("/api/kiosks/heartbeat/")
        request.META["HTTP_AUTHORIZATION"] = "Bearer fake_firebase_token"

        result = self.auth.authenticate(request)
        kiosk, _ = result

        # Verify kiosk_id is stored exactly as provided
        assert kiosk.kiosk_id == "BUS_ALPHA_KIOSK_001"
        assert kiosk.firebase_uid == "firebase_test_uid_004"

    def test_no_token_returns_none(self):
        """Test that request without token returns None"""
        request = self.factory.get("/api/kiosks/heartbeat/")
        # No Authorization header

        result = self.auth.authenticate(request)

        assert result is None

    def test_invalid_token_format_returns_none(self):
        """Test that invalid token format returns None"""
        request = self.factory.get("/api/kiosks/heartbeat/")
        request.META["HTTP_AUTHORIZATION"] = "InvalidFormat token123"

        result = self.auth.authenticate(request)

        assert result is None

    @patch("bus_kiosk_backend.core.authentication.auth.verify_id_token")
    def test_expired_token_raises_error(self, mock_verify):
        """Test that expired Firebase token raises authentication error"""
        from firebase_admin import auth as firebase_auth
        from rest_framework.exceptions import AuthenticationFailed

        mock_verify.side_effect = firebase_auth.ExpiredIdTokenError("Token expired", "cause")

        request = self.factory.get("/api/kiosks/heartbeat/")
        request.META["HTTP_AUTHORIZATION"] = "Bearer expired_token"

        with pytest.raises(AuthenticationFailed, match="expired"):
            self.auth.authenticate(request)


@pytest.mark.django_db
class TestKioskAPIAccess:
    """Test that auto-created kiosks can access API endpoints"""

    def setup_method(self):
        """Set up test client"""
        self.client = APIClient()

    @patch("bus_kiosk_backend.core.authentication.auth.verify_id_token")
    def test_kiosk_can_access_api_after_creation(self, mock_verify):
        """Test that auto-created kiosk can make authenticated requests"""
        from django.test import RequestFactory

        mock_verify.return_value = {"uid": "firebase_test_uid_005", "email": "kiosk005@easypool.in", "type": "kiosk", "kiosk_id": "TEST_KIOSK_005"}

        # Test authentication directly (avoid URL routing issues)
        factory = RequestFactory()
        auth = FirebaseAuthentication()

        request = factory.get("/api/test/")
        request.META["HTTP_AUTHORIZATION"] = "Bearer fake_firebase_token"

        result = auth.authenticate(request)
        kiosk, _ = result

        # Should authenticate successfully
        assert kiosk is not None
        assert isinstance(kiosk, Kiosk)

        # Verify kiosk was created
        kiosk = Kiosk.objects.get(kiosk_id="TEST_KIOSK_005")
        assert kiosk.is_active is False


@pytest.mark.django_db
class TestKioskActivation:
    """Test kiosk activation workflow"""

    def test_admin_can_activate_kiosk(self):
        """Test that admin can activate an inactive kiosk"""
        # Create inactive kiosk
        kiosk = Kiosk.objects.create(kiosk_id="TEST_KIOSK_006", firebase_uid="firebase_test_uid_006", is_active=False)

        assert kiosk.is_active is False

        # Admin activates kiosk
        kiosk.is_active = True
        kiosk.save()

        # Verify activation
        kiosk.refresh_from_db()
        assert kiosk.is_active is True


# Run tests with: pytest backend_easy/tests/test_firebase_kiosk_auth.py -v
