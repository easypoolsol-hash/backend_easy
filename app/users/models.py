import uuid

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Role(models.Model):
    """Role model for RBAC (Role-Based Access Control)"""

    ROLE_CHOICES = [
        ("super_admin", "Super Administrator"),
        ("backend_engineer", "Backend Engineer"),
        ("school_admin", "School Administrator"),
        ("parent", "Parent"),
    ]

    role_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, choices=ROLE_CHOICES, unique=True)
    description = models.TextField(blank=True)
    permissions = models.JSONField(
        default=dict, help_text="JSON object defining role permissions"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "roles"
        indexes = [
            models.Index(
                fields=["name"],
                condition=models.Q(is_active=True),
                name="idx_roles_active",
            ),
        ]

    def __str__(self):
        return self.get_name_display()


class UserManager(BaseUserManager):
    """Custom manager for User model"""

    def create_user(self, username, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        if not username:
            raise ValueError("Username is required")

        email = self.normalize_email(email)
        # Set default role if not provided
        if "role" not in extra_fields:
            try:
                extra_fields["role"] = Role.objects.get_or_create(
                    name="backend_engineer"
                )[0]
            except Exception:
                # If Role table doesn't exist yet, skip setting role
                pass

        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)  # type: ignore[attr-defined]
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        # Set default role if not provided
        if "role" not in extra_fields:
            try:
                extra_fields.setdefault(
                    "role", Role.objects.get_or_create(name="super_admin")[0]
                )
            except Exception:
                # If Role table doesn't exist yet, skip setting role
                pass

        return self.create_user(username, email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Extended user model for the bus kiosk system"""

    user_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="users")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # For Django admin access
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        db_table = "users"
        indexes = [
            models.Index(fields=["email"], name="idx_users_email"),
            models.Index(
                fields=["role"],
                condition=models.Q(is_active=True),
                name="idx_users_role_active",
            ),
        ]

    def __str__(self):
        return f"{self.username} ({self.email})"

    def clean(self):
        if self.role and self.role.name not in dict(Role.ROLE_CHOICES):
            raise ValidationError(f"Invalid role: {self.role.name}")

    @property
    def is_super_admin(self):
        return self.role.name == "super_admin"

    @property
    def is_backend_engineer(self):
        return self.role.name == "backend_engineer"

    @property
    def is_school_admin(self):
        return self.role.name == "school_admin"

    @property
    def is_parent(self):
        return self.role.name == "parent"


class APIKey(models.Model):
    """API Key model for kiosk device authentication"""

    key_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kiosk_id = models.CharField(max_length=100, help_text="Reference to kiosk device")
    key_hash = models.CharField(max_length=255, unique=True, help_text="Hashed API key")
    name = models.CharField(
        max_length=100, blank=True, help_text="Human-readable name for the key"
    )
    permissions = models.JSONField(
        default=dict, help_text="JSON object defining scoped permissions"
    )
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
        return self.expires_at and timezone.now() > self.expires_at


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
    changes = models.JSONField(
        null=True, blank=True, help_text="JSON object of changes made"
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "audit_log"
        indexes = [
            models.Index(fields=["user", "-timestamp"], name="idx_audit_user_time"),
            models.Index(
                fields=["resource_type", "resource_id"], name="idx_audit_resource"
            ),
            models.Index(fields=["-timestamp"], name="idx_audit_timestamp"),
        ]
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.action} {self.resource_type} by {self.user} at {self.timestamp}"
