from django.contrib import admin
from django.contrib.admin import display
from django.utils.html import format_html

from .models import (
    BusLocation,
    DeviceLog,
    Kiosk,
    KioskStatus,
    SOSAlert,
)
from .models_operation_timing import OperationSlot, OperationTiming


class OperationSlotInline(admin.TabularInline):
    """Inline for adding time slots to operation timings"""

    model = OperationSlot
    extra = 1
    fields = ["start_time", "end_time", "order"]
    ordering = ["order", "start_time"]

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """Override time fields to use HTML5 time input"""
        if db_field.name in ["start_time", "end_time"]:
            kwargs["widget"] = admin.widgets.AdminTimeWidget(attrs={"type": "time"})
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(OperationTiming)
class OperationTimingAdmin(admin.ModelAdmin):
    """Admin for operation timings"""

    list_display = ["name", "slots_display", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "description"]
    inlines = [OperationSlotInline]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (
            "Basic Info",
            {
                "fields": ("name", "description", "is_active"),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    @display(description="Time Slots")
    def slots_display(self, obj):
        """Display time slots"""
        slots = obj.slots.all()
        if not slots:
            return format_html('<span style="color: gray;">No slots</span>')

        slot_html = " | ".join(
            [f'<span style="color: green;">{slot.start_time.strftime("%H:%M")} - {slot.end_time.strftime("%H:%M")}</span>' for slot in slots]
        )
        return format_html(slot_html)


@admin.register(Kiosk)
class KioskAdmin(admin.ModelAdmin):
    """Admin interface for kiosks"""

    list_display = [
        "kiosk_id",
        "bus",
        "status_display",
        "firmware_version",
        "git_commit_sha_display",
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
        (
            "Device Info",
            {
                "fields": ("kiosk_id", "firebase_uid", "bus", "is_active"),
                "description": "Pre-register kiosk before deployment. firebase_uid must match Firebase Authentication UID.",
            },
        ),
        (
            "Bus Schedule",
            {
                "fields": ("operation_timing",),
                "description": "Select operation schedule from predefined timings. Create timings in Operation Timings section.",
            },
        ),
        (
            "Technical Details",
            {
                "fields": (
                    "firmware_version",
                    "git_commit_sha",
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

    @display(description="Git SHA")
    def git_commit_sha_display(self, obj):
        """Display short git commit SHA"""
        if not obj.git_commit_sha:
            return format_html('<span style="color: gray;">—</span>')
        # Show first 7 characters (short SHA)
        short_sha = obj.git_commit_sha[:7]
        return format_html(
            '<code style="background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-family: monospace;">{}</code>',
            short_sha,
        )

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


@admin.register(BusLocation)
class BusLocationAdmin(admin.ModelAdmin):
    """Admin interface for GPS location tracking"""

    BUS_ICON_SVG_PATH = (
        "M12 2C10.9 2 10 2.9 10 4H6C4.9 4 4 4.9 4 6V17C4 18.1 4.9 19 6 19H7V20C7 "
        "20.6 7.4 21 8 21C8.6 21 9 20.6 9 20V19H15V20C15 20.6 15.4 21 16 21C16.6 "
        "21 17 20.6 17 20V19H18C19.1 19 20 18.1 20 17V6C20 4.9 19.1 4 18 4H14C14 "
        "2.9 13.1 2 12 2M6 8H18V14H6V8Z"
    )

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
        """Show map with custom yellow bus icon"""

        from django.conf import settings

        api_key = getattr(settings, "GOOGLE_MAPS_API_KEY", "")

        if not api_key:
            return format_html(
                '<div style="padding: 20px; background: #f5f5f5; '
                'border-radius: 5px; text-align: center;">'
                "<p>Google Maps API Key not configured</p>"
                '<p><a href="https://www.google.com/maps?q={},{} " '
                'target="_blank">View on Google Maps</a></p>'
                "</div>",
                obj.latitude,
                obj.longitude,
            )

        # Modern map with yellow bus icon (AdvancedMarkerElement)

        map_id = f"map_{obj.location_id}"

        return format_html(
            '<div id="{}" style="width:100%; height:300px;"></div>'
            "<script>"
            "(function() {{"
            "  if (window.initMap_{}_done) return;"
            "  window.initMap_{}_done = true;"
            '  const script = document.createElement("script");'
            '  script.src = "https://maps.googleapis.com/maps/api/js?key={}&libraries=marker&loading=async&callback=initMap_{}";'
            "  script.async = true;"
            "  script.defer = true;"
            "  document.head.appendChild(script);"
            "}})();"
            "async function initMap_{}() {{"
            '  const {{ Map }} = await google.maps.importLibrary("maps");'
            '  const {{ AdvancedMarkerElement, PinElement }} = await google.maps.importLibrary("marker");'
            "  const pos = {{ lat: {}, lng: {} }};"
            '  const map = new Map(document.getElementById("{}"), {{'
            '    zoom: 15, center: pos, mapId: "BUS_LOCATION_MAP"'
            "  }});"
            '  const busSvg = document.createElementNS("http://www.w3.org/2000/svg", "svg");'
            '  busSvg.setAttribute("width", "32");'
            '  busSvg.setAttribute("height", "32");'
            '  busSvg.setAttribute("viewBox", "0 0 24 24");'
            '  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");'
            '  path.setAttribute("d", "{svg_path}");'
            '  path.setAttribute("fill", "#FFD700");'
            '  path.setAttribute("stroke", "#FFA500");'
            '  path.setAttribute("stroke-width", "1");'
            "  busSvg.appendChild(path);"
            '  new AdvancedMarkerElement({{ map: map, position: pos, content: busSvg, title: "Bus Location" }});'
            "}}"
            "</script>",
            map_id,
            map_id,
            map_id,
            api_key,
            map_id,
            map_id,
            obj.latitude,
            obj.longitude,
            map_id,
            svg_path=self.BUS_ICON_SVG_PATH,
        )

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related("kiosk__bus")

    # Prevent manual editing - GPS logs come from kiosk devices
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SOSAlert)
class SOSAlertAdmin(admin.ModelAdmin):
    """Admin interface for SOS emergency alerts"""

    list_display = [
        "alert_id",
        "kiosk",
        "bus_info",
        "status_badge",
        "coordinates_display",
        "created_at",
        "acknowledged_by",
    ]

    list_filter = ["status", "created_at", "kiosk__kiosk_id"]

    search_fields = [
        "kiosk__kiosk_id",
        "kiosk__bus__license_plate",
        "message",
        "acknowledged_by",
        "resolved_by",
    ]

    readonly_fields = ["alert_id", "created_at", "map_preview"]

    date_hierarchy = "created_at"

    ordering = ["-created_at"]

    fieldsets = (
        (
            "Alert Info",
            {
                "fields": (
                    "alert_id",
                    "kiosk",
                    "created_at",
                    "status",
                )
            },
        ),
        (
            "Location",
            {
                "fields": (
                    "latitude",
                    "longitude",
                    "map_preview",
                )
            },
        ),
        (
            "Details",
            {
                "fields": (
                    "message",
                    "metadata",
                )
            },
        ),
        (
            "Response Tracking",
            {
                "fields": (
                    "acknowledged_at",
                    "acknowledged_by",
                    "resolved_at",
                    "resolved_by",
                )
            },
        ),
    )

    @display(description="Bus")
    def bus_info(self, obj):
        """Display bus information"""
        if obj.kiosk.bus:
            return f"{obj.kiosk.bus.bus_number} - {obj.kiosk.bus.license_plate}"
        return "No bus assigned"

    @display(description="Status")
    def status_badge(self, obj):
        """Display status with color badge"""
        colors = {
            "active": "red",
            "acknowledged": "orange",
            "resolved": "green",
            "false_alarm": "gray",
        }
        color = colors.get(obj.status, "gray")
        icon = "🚨" if obj.status == "active" else "✓"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color,
            icon,
            obj.get_status_display().upper(),
        )

    @display(description="Coordinates")
    def coordinates_display(self, obj):
        """Display GPS coordinates with link to Google Maps"""
        if obj.latitude is None or obj.longitude is None:
            return "No location"

        maps_url = f"https://www.google.com/maps?q={obj.latitude},{obj.longitude}"
        return format_html(
            '<a href="{}" target="_blank">📍 {:.6f}, {:.6f}</a>',
            maps_url,
            obj.latitude,
            obj.longitude,
        )

    @display(description="Map Preview")
    def map_preview(self, obj):
        """Show map with SOS alert location"""
        if obj.latitude is None or obj.longitude is None:
            return "No location data"

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

        map_id = f"sos_map_{obj.alert_id}"

        return format_html(
            '<div id="{}" style="width:100%; height:300px;"></div>'
            "<script>"
            "(function() {{"
            "  if (window.initSOSMap_{}_done) return;"
            "  window.initSOSMap_{}_done = true;"
            '  const script = document.createElement("script");'
            '  script.src = "https://maps.googleapis.com/maps/api/js?key={}&libraries=marker&loading=async&callback=initSOSMap_{}";'
            "  script.async = true;"
            "  script.defer = true;"
            "  document.head.appendChild(script);"
            "}})();"
            "async function initSOSMap_{}() {{"
            '  const {{ Map }} = await google.maps.importLibrary("maps");'
            '  const {{ AdvancedMarkerElement, PinElement }} = await google.maps.importLibrary("marker");'
            "  const pos = {{ lat: {}, lng: {} }};"
            '  const map = new Map(document.getElementById("{}"), {{'
            '    zoom: 15, center: pos, mapId: "SOS_ALERT_MAP"'
            "  }});"
            "  const pinBackground = new PinElement({{"
            '    background: "#DC2626",'
            '    borderColor: "#991B1B",'
            '    glyphColor: "white",'
            '    glyph: "⚠",'
            "    scale: 1.5"
            "  }});"
            '  new AdvancedMarkerElement({{ map: map, position: pos, content: pinBackground.element, title: "SOS Alert Location" }});'
            "}}"
            "</script>",
            map_id,
            obj.alert_id,
            obj.alert_id,
            api_key,
            obj.alert_id,
            obj.alert_id,
            obj.latitude,
            obj.longitude,
            map_id,
        )

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related("kiosk__bus")

    # Allow manual status updates for acknowledgment/resolution
    def has_add_permission(self, request):
        return False  # SOS alerts created by kiosks only
