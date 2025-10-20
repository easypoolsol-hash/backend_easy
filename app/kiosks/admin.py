from django.contrib import admin
from django.contrib.admin import display
from django.utils.html import format_html

from .models import (
    BusLocation,
    DeviceLog,
    Kiosk,
    KioskActivationToken,
    KioskStatus,
)


@admin.register(Kiosk)
class KioskAdmin(admin.ModelAdmin):
    """Admin interface for kiosks"""

    list_display = [
        "kiosk_id",
        "bus",
        "status_display",
        "firmware_version",
        "current_battery_display",
        "last_heartbeat",
        "is_online_display",
        "created_at",
    ]
    list_filter = ["is_active", "firmware_version", "bus__route", "created_at"]
    search_fields = ["kiosk_id", "bus__license_plate", "firmware_version"]
    readonly_fields = ["created_at", "updated_at", "last_heartbeat"]
    ordering = ["kiosk_id"]

    fieldsets = (
        ("Device Info", {"fields": ("kiosk_id", "bus", "is_active")}),
        (
            "Technical Details",
            {
                "fields": (
                    "firmware_version",
                    "battery_level",
                    "storage_used_mb",
                )
            },
        ),
        (
            "Status",
            {
                "fields": ("last_heartbeat", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    @display(description="Status")
    def status_display(self, obj):
        """Display comprehensive status with health indicators"""
        try:
            status = obj.status
            colors = {
                "ok": "green",
                "warning": "orange",
                "critical": "red",
            }
            color = colors.get(status.status, "gray")
            is_online = obj.is_online
            online_color = "green" if is_online else "red"
            online_text = "Online" if is_online else "Offline"

            return format_html(
                '<span style="color: {}; font-weight: bold;">● {}</span> | <span style="color: {};">● {}</span>',
                color,
                status.get_status_display().upper(),
                online_color,
                online_text,
            )
        except KioskStatus.DoesNotExist:
            # No status yet - show only online status
            is_online = obj.is_online
            color = "green" if is_online else "red"
            text = "Online" if is_online else "Offline"
            return format_html('<span style="color: {};">● {}</span>', color, text)

    @display(description="Online Status")
    def is_online_display(self, obj):
        """Display online status with color coding"""
        if obj.is_online:
            return format_html('<span style="color: green;">● Online</span>')
        else:
            return format_html('<span style="color: red;">● Offline</span>')

    @display(description="Battery")
    def current_battery_display(self, obj):
        """Display current battery level from KioskStatus."""
        try:
            status = obj.status  # Access the related KioskStatus
            if status.battery_level is None:
                return "—"
            icon = "🔌" if status.is_charging else "⚡"
            return format_html(
                '<span style="font-weight: bold;">{}% {}</span>',
                status.battery_level,
                icon,
            )
        except KioskStatus.DoesNotExist:
            # Fallback to old battery_level field if no status exists
            if obj.battery_level is None:
                return "—"
            return f"{obj.battery_level}% ⚠️"

    # short_description provided by decorator

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related("bus")

    actions = ["mark_active", "mark_inactive", "generate_activation_token"]

    @admin.action(description="Generate Activation Tokens")
    def generate_activation_token(self, request, queryset):
        """Generate activation tokens for selected kiosks"""
        from django.contrib import messages

        tokens = []
        for kiosk in queryset:
            raw_token, _ = KioskActivationToken.generate_for_kiosk(kiosk)
            tokens.append(f"{kiosk.kiosk_id}: {raw_token}")

        # Show tokens to admin (copy to clipboard - won't show again!)
        message_lines = [
            "⚠️ ACTIVATION TOKENS (COPY NOW - Won't show again):",
            "",
        ]
        message_lines.extend(tokens)
        message_lines.append("")
        message_lines.append("Send tokens to technicians via secure channel")
        message = "\n".join(message_lines)
        self.message_user(request, message, level=messages.WARNING)

    # admin.action used for description


@admin.register(DeviceLog)
class DeviceLogAdmin(admin.ModelAdmin):
    """Admin interface for device logs"""

    list_display = [
        "kiosk",
        "log_level",
        "timestamp",
        "message_preview",
        "has_metadata",
    ]
    list_filter = ["log_level", "kiosk__kiosk_id", "timestamp"]
    search_fields = ["kiosk__kiosk_id", "message"]
    readonly_fields = ["log_id", "timestamp"]
    date_hierarchy = "timestamp"
    ordering = ["-timestamp"]

    fieldsets = (
        ("Log Info", {"fields": ("log_id", "kiosk", "timestamp")}),
        ("Content", {"fields": ("log_level", "message", "metadata")}),
    )

    @display(description="Message")
    def message_preview(self, obj):
        """Show first 50 characters of message"""
        preview = obj.message
        if len(preview) > 50:
            return preview[:50] + "..."
        return preview

    @display(description="Has Metadata", boolean=True)
    def has_metadata(self, obj):
        """Check if log entry has metadata"""
        return bool(obj.metadata)

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related("kiosk")

    # Prevent adding/editing logs manually - they should come from devices
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(KioskStatus)
class KioskStatusAdmin(admin.ModelAdmin):
    """Admin interface for kiosk sync status"""

    list_display = [
        "kiosk_id_display",
        "status_badge",
        "database_version",
        "student_count",
        "embedding_count",
        "battery_display",
        "last_heartbeat",
        "is_outdated_display",
    ]
    list_filter = ["status", "is_charging", "network_type"]
    search_fields = ["kiosk__kiosk_id"]
    readonly_fields = ["kiosk", "updated_at"]
    ordering = ["-last_heartbeat"]

    fieldsets = (
        ("Kiosk", {"fields": ("kiosk",)}),
        (
            "Database Sync",
            {
                "fields": (
                    "database_version",
                    "database_hash",
                    "student_count",
                    "embedding_count",
                )
            },
        ),
        (
            "Health Metrics",
            {
                "fields": (
                    "battery_level",
                    "is_charging",
                    "storage_available_mb",
                    "camera_active",
                    "network_type",
                    "app_version",
                )
            },
        ),
        (
            "Activity",
            {
                "fields": (
                    "last_face_detected",
                    "faces_detected_today",
                    "students_identified_today",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "status",
                    "last_error",
                    "last_heartbeat",
                    "updated_at",
                )
            },
        ),
    )

    @display(description="Kiosk ID")
    def kiosk_id_display(self, obj):
        """Display kiosk ID"""
        return obj.kiosk.kiosk_id

    @display(description="Status")
    def status_badge(self, obj):
        """Display status with color badge"""
        colors = {
            "ok": "green",
            "warning": "orange",
            "critical": "red",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">● {}</span>',
            color,
            obj.get_status_display(),
        )

    @display(description="Battery")
    def battery_display(self, obj):
        """Display battery level with charging indicator"""
        if obj.battery_level is None:
            return "—"
        icon = "🔌" if obj.is_charging else "⚡"
        return f"{obj.battery_level}% {icon}"

    # short_description via decorator

    @display(description="DB Status")
    def is_outdated_display(self, obj):
        """Display if database is outdated"""
        if obj.is_outdated:
            return format_html('<span style="color: red;">● Outdated</span>')
        return format_html('<span style="color: green;">● Current</span>')

    # short_description via decorator

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related("kiosk__bus")

    # Prevent manual editing - should be updated via heartbeat API
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(KioskActivationToken)
class KioskActivationTokenAdmin(admin.ModelAdmin):
    """Admin interface for kiosk activation tokens"""

    list_display = [
        "kiosk",
        "status_badge",
        "created_at",
        "expires_at",
        "used_at",
        "used_by_ip",
    ]
    list_filter = ["is_used", "created_at", "expires_at"]
    search_fields = ["kiosk__kiosk_id"]
    readonly_fields = [
        "kiosk",
        "token_hash",
        "created_at",
        "used_at",
        "used_by_ip",
    ]
    ordering = ["-created_at"]

    fieldsets = (
        (
            "Token Info",
            {"fields": ("kiosk", "token_hash", "created_at", "expires_at")},
        ),
        ("Usage", {"fields": ("is_used", "used_at", "used_by_ip")}),
    )

    @display(description="Status")
    def status_badge(self, obj):
        """Display status with color badge"""
        if obj.is_used:
            color = "red"
            text = "USED"
        elif obj.is_valid():
            color = "green"
            text = "VALID"
        else:
            color = "gray"
            text = "EXPIRED"
        return format_html(
            ('<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>'),
            color,
            text,
        )

    # decorator sets short_description

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related("kiosk")

    # Prevent manual creation/editing -
    # tokens should be generated via admin action
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(BusLocation)
class BusLocationAdmin(admin.ModelAdmin):
    """Admin interface for GPS location tracking"""

    list_display = [
        "kiosk",
        "coordinates_display",
        "speed",
        "accuracy",
        "timestamp",
        "created_at",
    ]
    list_filter = ["kiosk__kiosk_id", "timestamp", "created_at"]
    search_fields = ["kiosk__kiosk_id", "kiosk__bus__license_plate"]
    readonly_fields = ["location_id", "created_at", "map_preview"]
    date_hierarchy = "timestamp"
    ordering = ["-timestamp"]

    fieldsets = (
        ("Location Info", {"fields": ("location_id", "kiosk", "timestamp")}),
        (
            "GPS Coordinates",
            {
                "fields": (
                    "latitude",
                    "longitude",
                    "accuracy",
                    "speed",
                    "heading",
                    "map_preview",
                )
            },
        ),
        ("Metadata", {"fields": ("created_at",)}),
    )

    @display(description="Coordinates")
    def coordinates_display(self, obj):
        """Display GPS coordinates with link to Google Maps"""
        maps_url = f"https://www.google.com/maps?q={obj.latitude},{obj.longitude}"
        lat_str = f"{obj.latitude:.6f}"
        lng_str = f"{obj.longitude:.6f}"
        return format_html(
            '<a href="{}" target="_blank">{}, {}</a>',
            maps_url,
            lat_str,
            lng_str,
        )

    @display(description="Map Preview")
    def map_preview(self, obj):
        """Show embedded map preview if Google Maps API key is available"""
        from django.conf import settings

        api_key = getattr(settings, "GOOGLE_MAPS_API_KEY", "")
        if not api_key:
            return format_html(
                '<div style="padding: 20px; background: #f5f5f5; '
                'border-radius: 5px; text-align: center;">'
                "<p>Google Maps API Key not configured</p>"
                '<p><a href="https://www.google.com/maps?q={},{}" '
                'target="_blank">View on Google Maps</a></p>'
                "</div>",
                obj.latitude,
                obj.longitude,
            )

        return format_html(
            '<iframe width="100%" height="300" frameborder="0" '
            'style="border:0" src="https://www.google.com/maps/embed/v1/'
            'place?key={}&q={},{}&zoom=15" allowfullscreen></iframe>',
            api_key,
            obj.latitude,
            obj.longitude,
        )

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related("kiosk__bus")

    # Prevent manual editing - GPS logs come from kiosk devices
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
