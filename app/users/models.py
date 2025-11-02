import uuid

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    Group,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Custom manager for User model"""

    def create_user(self, username, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        if not username:
            raise ValueError("Username is required")

        email = self.normalize_email(email)

        # user_id (UUID) auto-generates via default=uuid.uuid4
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)  # type: ignore[attr-defined]
        user.save(using=self._db)

        # Assign default group for new users (no permissions)
        if not user.groups.exists():
            try:
                default_group, _ = Group.objects.get_or_create(name="New User")
                user.groups.add(default_group)
            except Exception:  # nosec B110
                # If Group table doesn't exist yet, skip setting group
                pass

        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        # user_id (UUID) auto-generates via default=uuid.uuid4
        user = self.create_user(username, email, password, **extra_fields)

        # Assign super admin group
        try:
            super_admin_group, _ = Group.objects.get_or_create(name="Super Administrator")
            user.groups.add(super_admin_group)
        except Exception:  # nosec B110
            # If Group table doesn't exist yet, skip setting group
            pass

        return user


class User(AbstractBaseUser, PermissionsMixin):
    """
    Extended user model for the bus kiosk system.

    Uses Django's built-in Groups for RBAC (battery-included approach).
    Groups are managed via django.contrib.auth.models.Group.

    Available groups (created via management command):
    - Super Administrator: Full system access
    - Backend Engineer: Read-only production access
    - School Administrator: Full control within assigned school
    - Parent: View own children and bus tracking
    - New User: No permissions (default for Firebase-authenticated users)
    """

    # UUID primary key - auto-generates for all users (Firebase, manual, any source)
    user_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True, default="")
    last_name = models.CharField(max_length=150, blank=True, default="")
    # Note: groups and user_permissions come from PermissionsMixin
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # For Django admin access
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    @property
    def id(self):
        """Alias for user_id to support JWT libraries expecting 'id'"""
        return self.user_id

    class Meta:
        db_table = "users"
        indexes = [
            models.Index(fields=["email"], name="idx_users_email"),
            models.Index(fields=["username"], name="idx_users_username"),
        ]

    def __str__(self):
        return f"{self.username} ({self.email})"

    # Helper properties for role checking (backwards compatible)
    @property
    def is_super_admin(self):
        """Check if user is in Super Administrator group"""
        return self.groups.filter(name="Super Administrator").exists()

    @property
    def is_backend_engineer(self):
        """Check if user is in Backend Engineer group"""
        return self.groups.filter(name="Backend Engineer").exists()

    @property
    def is_school_admin(self):
        """Check if user is in School Administrator group"""
        return self.groups.filter(name="School Administrator").exists()

    @property
    def is_parent(self):
        """Check if user is in Parent group"""
        return self.groups.filter(name="Parent").exists()

    @property
    def role_name(self):
        """
        Get primary role name for backwards compatibility.
        Returns the first group name or None.
        """
        first_group = self.groups.first()
        return first_group.name if first_group else None


class APIKey(models.Model):
    """API Key model for kiosk device authentication"""

    key_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kiosk_id = models.CharField(max_length=100, help_text="Reference to kiosk device")
    key_hash = models.CharField(max_length=255, unique=True, help_text="Hashed API key")
    name = models.CharField(max_length=100, blank=True, help_text="Human-readable name for the key")
    permissions = models.JSONField(default=dict, help_text="JSON object defining scoped permissions")
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "api_keys"
        indexes = [
            models.Index(fields=["kiosk_id"], name="idx_apikey_kiosk"),
            models.Index(
                fields=["is_active"],
                condition=models.Q(is_active=True),
                name="idx_apikey_active",
            ),
        ]

    def __str__(self):
        return f"API Key for {self.kiosk_id}"

    def is_expired(self):
        return self.expires_at is not None and timezone.now() > self.expires_at


class AuditLog(models.Model):
    """Immutable audit trail for compliance (7-year retention)"""

    ACTION_CHOICES = [
        ("CREATE", "Create"),
        ("UPDATE", "Update"),
        ("DELETE", "Delete"),
        ("LOGIN", "Login"),
        ("LOGOUT", "Logout"),
        ("API_ACCESS", "API Access"),
    ]

    RESOURCE_CHOICES = [
        ("user", "User"),
        ("student", "Student"),
        ("bus", "Bus"),
        ("kiosk", "Kiosk"),
        ("event", "Boarding Event"),
        ("notification", "Notification"),
    ]

    log_id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100, choices=ACTION_CHOICES)
    resource_type = models.CharField(max_length=50, choices=RESOURCE_CHOICES)
    resource_id = models.CharField(max_length=100, blank=True)
    changes = models.JSONField(null=True, blank=True, help_text="JSON object of changes made")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "audit_log"
        indexes = [
            models.Index(fields=["user", "-timestamp"], name="idx_audit_user_time"),
            models.Index(fields=["resource_type", "resource_id"], name="idx_audit_resource"),
            models.Index(fields=["-timestamp"], name="idx_audit_timestamp"),
        ]
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.action} {self.resource_type} by {self.user} at {self.timestamp}"
