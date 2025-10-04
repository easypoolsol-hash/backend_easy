from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import APIKey, AuditLog, Role, User


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['role_id', 'created_at', 'updated_at']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'role', 'is_active', 'last_login']
    list_filter = ['role', 'is_active', 'is_staff', 'created_at']
    search_fields = ['username', 'email']
    readonly_fields = ['user_id', 'last_login', 'created_at', 'updated_at']

    fieldsets = (
        *BaseUserAdmin.fieldsets,
        ('Bus Kiosk Fields', {
            'fields': ('role', 'user_id', 'created_at', 'updated_at')
        }),
    )

    add_fieldsets = (
        *BaseUserAdmin.add_fieldsets,
        ('Bus Kiosk Fields', {
            'fields': ('email', 'role')
        }),
    )


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ['kiosk_id', 'name', 'is_active', 'expires_at', 'last_used']
    list_filter = ['is_active', 'expires_at', 'created_at']
    search_fields = ['kiosk_id', 'name', 'key_hash']
    readonly_fields = ['key_id', 'key_hash', 'last_used', 'created_at']

    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing existing object
            return ['key_id', 'key_hash', 'last_used', 'created_at']
        return ['key_id', 'created_at']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = [
        'timestamp', 'user', 'action', 'resource_type', 'resource_id'
    ]
    list_filter = ['action', 'resource_type', 'timestamp']
    search_fields = ['user__username', 'resource_id', 'action']
    readonly_fields = ['log_id', 'timestamp']

    def has_add_permission(self, request):
        return False  # Audit logs should not be manually created

    def has_change_permission(self, request, obj=None):
        return False  # Audit logs should not be edited

    def has_delete_permission(self, request, obj=None):
        return False  # Audit logs should not be deleted
