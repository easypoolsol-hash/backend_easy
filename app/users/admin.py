from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group

from .models import APIKey, AuditLog, User

# Unregister default Group admin and register custom one
admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin):
    """
    Custom Group admin - READ ONLY for all users.
    Groups should only be modified via management commands (IAM principle).
    """

    def has_add_permission(self, request):
        return False  # Cannot create groups via admin panel

    def has_change_permission(self, request, obj=None):
        return False  # Cannot modify groups via admin panel

    def has_delete_permission(self, request, obj=None):
        return False  # Cannot delete groups via admin panel


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom User admin using Django's built-in Groups (battery-included).
    Groups (roles) are managed via seed_groups.py management command.
    """

    list_display = ["username", "email", "get_groups", "is_active", "last_login"]
    list_filter = ["groups", "is_active", "is_staff", "created_at"]
    search_fields = ["username", "email"]
    readonly_fields = ["user_id", "last_login", "created_at", "updated_at"]

    def get_groups(self, obj):
        """Display user's groups (roles)"""
        return ", ".join([g.name for g in obj.groups.all()]) or "No groups"

    get_groups.short_description = "Groups (Roles)"  # type: ignore[attr-defined]

    fieldsets = (
        *BaseUserAdmin.fieldsets,  # type: ignore[misc]
        (
            "Bus Kiosk Fields",
            {"fields": ("user_id", "created_at", "updated_at")},
        ),
    )

    add_fieldsets = (
        *BaseUserAdmin.add_fieldsets,
        ("Bus Kiosk Fields", {"fields": ("email",)}),
    )


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ["kiosk_id", "name", "is_active", "expires_at", "last_used"]
    list_filter = ["is_active", "expires_at", "created_at"]
    search_fields = ["kiosk_id", "name", "key_hash"]
    readonly_fields = ["key_id", "key_hash", "last_used", "created_at"]

    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing existing object
            return ["key_id", "key_hash", "last_used", "created_at"]
        return ["key_id", "created_at"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "user", "action", "resource_type", "resource_id"]
    list_filter = ["action", "resource_type", "timestamp"]
    search_fields = ["user__username", "resource_id", "action"]
    readonly_fields = ["log_id", "timestamp"]

    def has_add_permission(self, request):
        return False  # Audit logs should not be manually created

    def has_change_permission(self, request, obj=None):
        return False  # Audit logs should not be edited

    def has_delete_permission(self, request, obj=None):
        return False  # Audit logs should not be deleted
