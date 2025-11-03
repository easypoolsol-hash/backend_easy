"""
Last Login Tracking Tests

Tests that last_login is properly updated across all authentication methods:
- Firebase authentication (REST API)
- Session-based authentication (Django admin)
- WebSocket authentication
- Audit log creation for login history
"""

from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.utils import timezone
import pytest
from rest_framework.test import APIRequestFactory

from bus_kiosk_backend.core.authentication import FirebaseAuthentication
from users.models import AuditLog
from users.signals import user_authenticated

User = get_user_model()


@pytest.mark.django_db
class TestLastLoginTracking:
    """Test last_login tracking across all authentication methods"""

    def test_firebase_auth_updates_last_login_on_first_login(self):
        """Firebase authentication should update last_login on first authentication"""
        # Mock Firebase token verification
        with patch("bus_kiosk_backend.core.authentication.auth.verify_id_token") as mock_verify:
            mock_verify.return_value = {
                "uid": "firebase_new_user_123",
                "email": "newuser@school.com",
                "name": "Jane Smith",
            }

            factory = APIRequestFactory()
            request = factory.get("/api/v1/users/me/", HTTP_AUTHORIZATION="Bearer valid_token")

            auth = FirebaseAuthentication()
            user, _ = auth.authenticate(request)

            # Verify last_login was set
            assert user.last_login is not None
            assert (timezone.now() - user.last_login).total_seconds() < 5  # Within 5 seconds

            # Verify audit log was created
            audit_logs = AuditLog.objects.filter(user=user, action="LOGIN")
            assert audit_logs.exists()

            latest_log = audit_logs.latest("timestamp")
            assert latest_log.changes["auth_method"] == "firebase"
            assert latest_log.resource_type == "user"

    def test_firebase_auth_throttles_last_login_updates(self):
        """Firebase authentication should throttle last_login updates (5 min interval)"""
        # Create user with recent last_login
        initial_login_time = timezone.now() - timedelta(minutes=2)
        user = User.objects.create_user(
            username="firebase_existing_user",
            email="existing@school.com",
            password="testpass123",
        )
        user.last_login = initial_login_time
        user.save()

        # Get initial audit log count
        initial_audit_count = AuditLog.objects.filter(user=user, action="LOGIN").count()

        # Mock Firebase token verification
        with patch("bus_kiosk_backend.core.authentication.auth.verify_id_token") as mock_verify:
            mock_verify.return_value = {
                "uid": "firebase_existing_user",
                "email": "existing@school.com",
                "name": "Test User",
            }

            factory = APIRequestFactory()
            request = factory.get("/api/v1/users/me/", HTTP_AUTHORIZATION="Bearer valid_token")

            auth = FirebaseAuthentication()
            authenticated_user, _ = auth.authenticate(request)

            # Refresh from DB
            authenticated_user.refresh_from_db()

            # Last login should NOT be updated (less than 5 minutes)
            assert authenticated_user.last_login == initial_login_time

            # No new audit log should be created (throttled)
            new_audit_count = AuditLog.objects.filter(user=user, action="LOGIN").count()
            assert new_audit_count == initial_audit_count

    def test_firebase_auth_updates_after_throttle_period(self):
        """Firebase authentication should update last_login after throttle period (5+ minutes)"""
        # Create user with old last_login (6 minutes ago)
        old_login_time = timezone.now() - timedelta(minutes=6)
        user = User.objects.create_user(
            username="firebase_old_login_user",
            email="oldlogin@school.com",
            password="testpass123",
        )
        user.last_login = old_login_time
        user.save()

        # Mock Firebase token verification
        with patch("bus_kiosk_backend.core.authentication.auth.verify_id_token") as mock_verify:
            mock_verify.return_value = {
                "uid": "firebase_old_login_user",
                "email": "oldlogin@school.com",
                "name": "Test User",
            }

            factory = APIRequestFactory()
            request = factory.get("/api/v1/users/me/", HTTP_AUTHORIZATION="Bearer valid_token")

            auth = FirebaseAuthentication()
            authenticated_user, _ = auth.authenticate(request)

            # Refresh from DB
            authenticated_user.refresh_from_db()

            # Last login SHOULD be updated (more than 5 minutes)
            assert authenticated_user.last_login != old_login_time
            assert (timezone.now() - authenticated_user.last_login).total_seconds() < 5

            # New audit log should be created
            audit_logs = AuditLog.objects.filter(user=user, action="LOGIN")
            assert audit_logs.exists()

            latest_log = audit_logs.latest("timestamp")
            assert latest_log.changes["auth_method"] == "firebase"

    def test_custom_signal_updates_last_login(self):
        """Custom user_authenticated signal should update last_login"""
        user = User.objects.create_user(
            username="signal_test_user",
            email="signal@school.com",
            password="testpass123",
        )

        # Initial state: no last_login
        assert user.last_login is None

        # Create mock request
        request = Mock()
        request.META = {
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_USER_AGENT": "Mozilla/5.0",
        }

        # Emit signal
        user_authenticated.send(sender=self.__class__, user=user, request=request, auth_method="test")

        # Refresh from DB
        user.refresh_from_db()

        # Verify last_login was updated
        assert user.last_login is not None
        assert (timezone.now() - user.last_login).total_seconds() < 5

        # Verify audit log
        audit_log = AuditLog.objects.filter(user=user, action="LOGIN").latest("timestamp")
        assert audit_log.changes["auth_method"] == "test"
        assert audit_log.ip_address == "127.0.0.1"
        assert audit_log.user_agent == "Mozilla/5.0"

    def test_audit_log_tracks_ip_and_user_agent(self):
        """Audit log should capture IP address and user agent"""
        user = User.objects.create_user(
            username="audit_test_user",
            email="audit@school.com",
            password="testpass123",
        )

        # Create mock request with proxy headers
        request = Mock()
        request.META = {
            "HTTP_X_FORWARDED_FOR": "203.0.113.1, 198.51.100.1",
            "REMOTE_ADDR": "192.0.2.1",
            "HTTP_USER_AGENT": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0)",
        }

        # Emit signal
        user_authenticated.send(sender=self.__class__, user=user, request=request, auth_method="mobile")

        # Verify audit log captured correct IP (first in X-Forwarded-For)
        audit_log = AuditLog.objects.filter(user=user, action="LOGIN").latest("timestamp")
        assert audit_log.ip_address == "203.0.113.1"
        assert "iPhone" in audit_log.user_agent

    def test_multiple_login_methods_create_separate_audit_logs(self):
        """Different authentication methods should create separate audit log entries"""
        user = User.objects.create_user(
            username="multi_auth_user",
            email="multi@school.com",
            password="testpass123",
        )

        request = Mock()
        request.META = {"REMOTE_ADDR": "127.0.0.1", "HTTP_USER_AGENT": "Test"}

        # Login via different methods
        user_authenticated.send(sender=self.__class__, user=user, request=request, auth_method="firebase")
        user.last_login = None  # Reset to allow another update
        user.save()

        user_authenticated.send(sender=self.__class__, user=user, request=request, auth_method="websocket")

        # Verify separate audit logs
        audit_logs = AuditLog.objects.filter(user=user, action="LOGIN").order_by("timestamp")
        assert audit_logs.count() == 2

        methods = [log.changes["auth_method"] for log in audit_logs]
        assert "firebase" in methods
        assert "websocket" in methods

    def test_websocket_auth_with_no_request(self):
        """WebSocket authentication should handle None request gracefully"""
        user = User.objects.create_user(
            username="websocket_user",
            email="ws@school.com",
            password="testpass123",
        )

        # Emit signal without request (WebSocket scenario)
        user_authenticated.send(sender=self.__class__, user=user, request=None, auth_method="websocket")

        # Refresh from DB
        user.refresh_from_db()

        # Verify last_login was updated
        assert user.last_login is not None

        # Verify audit log was created with None IP/user_agent
        audit_log = AuditLog.objects.filter(user=user, action="LOGIN").latest("timestamp")
        assert audit_log.changes["auth_method"] == "websocket"
        assert audit_log.ip_address is None
        assert audit_log.user_agent == ""
