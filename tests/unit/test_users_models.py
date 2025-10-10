"""
Unit tests for users app models
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model

from users.models import APIKey, AuditLog
from tests.factories import UserFactory, RoleFactory

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    """Test User model properties and methods"""

    def test_is_parent_property(self):
        """Test the is_parent property"""
        parent_role = RoleFactory(name="parent")
        teacher_role = RoleFactory(name="teacher")

        parent_user = UserFactory(role=parent_role)
        teacher_user = UserFactory(role=teacher_role)

        assert parent_user.is_parent is True
        assert teacher_user.is_parent is False


@pytest.mark.django_db
class TestAPIKeyModel:
    """Test APIKey model"""

    def test_apikey_creation(self):
        """Test creating an APIKey instance"""
        apikey = APIKey.objects.create(
            kiosk_id="TEST-KIOSK-001",
            key_hash="hashed_key_value",
            name="Test Key",
            permissions={"read": True, "write": False}
        )

        assert str(apikey) == "API Key for TEST-KIOSK-001"
        assert apikey.is_active is True
        assert apikey.is_expired() is False

    def test_apikey_expiration(self):
        """Test APIKey expiration logic"""
        past_time = timezone.now() - timedelta(days=1)
        future_time = timezone.now() + timedelta(days=1)

        expired_key = APIKey.objects.create(
            kiosk_id="TEST-KIOSK-002",
            key_hash="expired_key",
            expires_at=past_time
        )

        valid_key = APIKey.objects.create(
            kiosk_id="TEST-KIOSK-003",
            key_hash="valid_key",
            expires_at=future_time
        )

        no_expiry_key = APIKey.objects.create(
            kiosk_id="TEST-KIOSK-004",
            key_hash="no_expiry_key"
        )

        assert expired_key.is_expired() is True
        assert valid_key.is_expired() is False
        assert no_expiry_key.is_expired() is False


@pytest.mark.django_db
class TestAuditLogModel:
    """Test AuditLog model"""

    def test_audit_log_creation(self):
        """Test creating an AuditLog instance"""
        user = UserFactory()
        audit_log = AuditLog.objects.create(
            user=user,
            action="CREATE",
            resource_type="user",
            resource_id=str(user.user_id),
            changes={"field": "value"},
            ip_address="192.168.1.1",
            user_agent="Test Agent"
        )

        assert str(audit_log).startswith("CREATE user by")
        assert audit_log.action == "CREATE"
        assert audit_log.resource_type == "user"
        assert audit_log.changes == {"field": "value"}

    def test_audit_log_without_user(self):
        """Test AuditLog without associated user"""
        audit_log = AuditLog.objects.create(
            action="DELETE",
            resource_type="student",
            resource_id="123",
            ip_address="10.0.0.1"
        )

        assert audit_log.user is None
        assert str(audit_log).startswith("DELETE student by None")
