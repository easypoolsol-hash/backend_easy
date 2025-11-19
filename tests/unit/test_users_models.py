"""
Unit tests for users app models
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
import pytest

from students.models import Parent
from tests.factories import UserFactory
from users.models import APIKey, AuditLog

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    """Test User model properties and methods"""

    def test_is_parent_property(self):
        """Test the is_parent property"""
        parent_user = UserFactory()
        parent_group, _ = Group.objects.get_or_create(name="Parent")
        parent_user.groups.add(parent_group)

        teacher_user = UserFactory()

        assert parent_user.is_parent is True
        assert teacher_user.is_parent is False


@pytest.mark.django_db
class TestAPIKeyModel:
    """Test APIKey model"""

    def test_apikey_creation(self):
        """Test creating an APIKey instance"""
        apikey = APIKey.objects.create(
            kiosk_id="TEST-KIOSK-001", key_hash="hashed_key_value", name="Test Key", permissions={"read": True, "write": False}
        )

        assert str(apikey) == "API Key for TEST-KIOSK-001"
        assert apikey.is_active is True
        assert apikey.is_expired() is False

    def test_apikey_expiration(self):
        """Test APIKey expiration logic"""
        past_time = timezone.now() - timedelta(days=1)
        future_time = timezone.now() + timedelta(days=1)

        expired_key = APIKey.objects.create(kiosk_id="TEST-KIOSK-002", key_hash="expired_key", expires_at=past_time)

        valid_key = APIKey.objects.create(kiosk_id="TEST-KIOSK-003", key_hash="valid_key", expires_at=future_time)

        no_expiry_key = APIKey.objects.create(kiosk_id="TEST-KIOSK-004", key_hash="no_expiry_key")

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
            user_agent="Test Agent",
        )

        assert str(audit_log).startswith("CREATE user by")
        assert audit_log.action == "CREATE"
        assert audit_log.resource_type == "user"
        assert audit_log.changes == {"field": "value"}

    def test_audit_log_without_user(self):
        """Test AuditLog without associated user"""
        audit_log = AuditLog.objects.create(action="DELETE", resource_type="student", resource_id="123", ip_address="10.0.0.1")

        assert audit_log.user is None
        assert str(audit_log).startswith("DELETE student by None")


@pytest.mark.django_db
class TestParentAutoCreationSignal:
    """Test auto-creation of Parent record when User is created"""

    def test_parent_auto_created_on_user_creation(self):
        """Test that Parent record is auto-created when new User is created"""
        # Create a new user (simulating Firebase signup)
        user = User.objects.create_user(username="testparent", email="testparent@example.com", password="testpass123")

        # Check that Parent was auto-created
        assert Parent.objects.filter(user=user).exists()

        parent = Parent.objects.get(user=user)
        assert parent.approval_status == "pending"
        assert parent.user == user
        assert "pending-" in parent.encrypted_email
        assert "+91" in parent.encrypted_phone
        assert "Pending User" in parent.encrypted_name

    def test_parent_not_created_on_user_update(self):
        """Test that Parent is not created again on user update"""
        # Create user
        user = User.objects.create_user(username="updatetest", email="updatetest@example.com", password="testpass123")

        # Get the auto-created parent
        parent = Parent.objects.get(user=user)
        parent_id = parent.parent_id

        # Update user
        user.email = "newemail@example.com"
        user.save()

        # Should still have only one parent with same ID
        assert Parent.objects.filter(user=user).count() == 1
        assert Parent.objects.get(user=user).parent_id == parent_id

    def test_signal_is_idempotent(self):
        """Test that signal doesn't create duplicate Parents"""
        # Create user with UserFactory (which might trigger signal)
        user = UserFactory()

        # Count parents
        initial_count = Parent.objects.filter(user=user).count()

        # Update user (should not create another parent)
        user.email = "newemail@example.com"
        user.save()

        # Count should be same
        final_count = Parent.objects.filter(user=user).count()
        assert initial_count == final_count
