from django.contrib import admin
from django.utils.html import format_html

from .models import DeviceLog, Kiosk


@admin.register(Kiosk)
class KioskAdmin(admin.ModelAdmin):
    """Admin interface for kiosks"""
    list_display = [
        'kiosk_id',
        'bus',
        'status_display',
        'firmware_version',
        'battery_level',
        'last_heartbeat',
        'is_online_display',
        'created_at'
    ]
    list_filter = [
        'is_active',
        'firmware_version',
        'bus__route',
        'created_at'
    ]
    search_fields = [
        'kiosk_id',
        'bus__license_plate',
        'firmware_version'
    ]
    readonly_fields = [
        'created_at',
        'updated_at',
        'last_heartbeat'
    ]
    ordering = ['kiosk_id']

    fieldsets = (
        ('Device Info', {
            'fields': ('kiosk_id', 'bus', 'is_active')
        }),
        ('Technical Details', {
            'fields': ('firmware_version', 'battery_level', 'storage_used_mb')
        }),
        ('Authentication', {
            'fields': ('api_key_hash',),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('last_heartbeat', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def is_online_display(self, obj):
        """Display online status with color coding"""
        if obj.is_online:
            return format_html('<span style="color: green;">● Online</span>')
        else:
            return format_html('<span style="color: red;">● Offline</span>')
    is_online_display.short_description = "Online Status"

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('bus')

    actions = ['mark_active', 'mark_inactive']

    def mark_active(self, request, queryset):
        """Mark selected kiosks as active"""
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} kiosks marked as active.")
    mark_active.short_description = "Mark selected kiosks as active"

    def mark_inactive(self, request, queryset):
        """Mark selected kiosks as inactive"""
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} kiosks marked as inactive.")
    mark_inactive.short_description = "Mark selected kiosks as inactive"


@admin.register(DeviceLog)
class DeviceLogAdmin(admin.ModelAdmin):
    """Admin interface for device logs"""
    list_display = [
        'kiosk',
        'log_level',
        'timestamp',
        'message_preview',
        'has_metadata'
    ]
    list_filter = [
        'log_level',
        'kiosk__kiosk_id',
        'timestamp'
    ]
    search_fields = [
        'kiosk__kiosk_id',
        'message'
    ]
    readonly_fields = [
        'log_id',
        'timestamp'
    ]
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']

    fieldsets = (
        ('Log Info', {
            'fields': ('log_id', 'kiosk', 'timestamp')
        }),
        ('Content', {
            'fields': ('log_level', 'message', 'metadata')
        }),
    )

    def message_preview(self, obj):
        """Show first 50 characters of message"""
        return obj.message[:50] + "..." if len(obj.message) > 50 else obj.message
    message_preview.short_description = "Message"

    def has_metadata(self, obj):
        """Check if log entry has metadata"""
        return bool(obj.metadata)
    has_metadata.boolean = True
    has_metadata.short_description = "Has Metadata"

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('kiosk')

    # Prevent adding/editing logs manually - they should come from devices
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
