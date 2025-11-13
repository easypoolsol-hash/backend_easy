from rest_framework import serializers

from .models import BusLocation, DeviceLog, Kiosk, KioskStatus, SOSAlert


class KioskSerializer(serializers.ModelSerializer):
    """Serializer for kiosks"""

    bus = serializers.CharField(source="bus.bus_id", read_only=True)
    bus_license_plate = serializers.CharField(source="bus.license_plate", read_only=True)
    status_display = serializers.ReadOnlyField()
    is_online = serializers.ReadOnlyField()
    battery_level = serializers.FloatField(required=False)

    class Meta:
        model = Kiosk
        fields = [
            "kiosk_id",
            "bus",
            "bus_license_plate",
            "firmware_version",
            "git_commit_sha",
            "last_heartbeat",
            "is_active",
            "battery_level",
            "storage_used_mb",
            "schedule",
            "status_display",
            "is_online",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["kiosk_id", "created_at", "updated_at"]

    def validate_battery_level(self, value):
        """Validate battery level is between 0 and 100"""
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError("Battery level must be between 0 and 100")
        return value


class KioskHeartbeatSerializer(serializers.Serializer):
    """
    Serializer for kiosk heartbeat data (Fortune 500 pattern)

    kiosk_id is optional - kiosk is authenticated via JWT.
    If provided, it's verified to match the authenticated kiosk (security check).
    """

    kiosk_id = serializers.CharField(max_length=100, required=False)
    firmware_version = serializers.CharField(max_length=50, required=False)
    battery_level = serializers.IntegerField(required=False, min_value=0, max_value=100)
    storage_used_mb = serializers.IntegerField(required=False, min_value=0)

    def validate_kiosk_id(self, value):
        """
        Optional security check: If kiosk_id provided, verify it matches authenticated kiosk.
        Prevents token reuse attacks.
        """
        # Get authenticated kiosk from context (set by view from request.user)
        authenticated_kiosk = self.context.get("kiosk")

        if authenticated_kiosk and value and value != authenticated_kiosk.kiosk_id:
            # Security violation: Firebase token doesn't match kiosk_id in request
            raise serializers.ValidationError("kiosk_id mismatch with authentication")

        return value


class DeviceLogSerializer(serializers.ModelSerializer):
    """Serializer for device logs"""

    kiosk_id = serializers.CharField(source="kiosk.kiosk_id", read_only=True)

    class Meta:
        model = DeviceLog
        fields = [
            "log_id",
            "kiosk",
            "kiosk_id",
            "log_level",
            "message",
            "metadata",
            "timestamp",
        ]
        read_only_fields = ["log_id", "timestamp"]


class CheckUpdatesSerializer(serializers.Serializer):
    """Serializer for check updates request"""

    last_sync_hash = serializers.CharField(required=False, allow_blank=True, help_text="Last content hash from kiosk")


class CheckUpdatesResponseSerializer(serializers.Serializer):
    """Serializer for check updates response"""

    needs_update = serializers.BooleanField(help_text="Whether kiosk needs to download new snapshot")
    current_version = serializers.CharField(help_text="Current database version timestamp")
    student_count = serializers.IntegerField(help_text="Number of students for this bus")
    embedding_count = serializers.IntegerField(help_text="Number of embeddings for this bus")
    content_hash = serializers.CharField(help_text="Content hash for integrity verification")


class SnapshotResponseSerializer(serializers.Serializer):
    """Serializer for snapshot download response"""

    download_url = serializers.URLField(help_text="Signed URL to download snapshot")
    checksum = serializers.CharField(help_text="SHA-256 checksum of snapshot")
    size_bytes = serializers.IntegerField(help_text="Size of snapshot in bytes")
    expires_at = serializers.DateTimeField(help_text="URL expiration time")


class HealthDataSerializer(serializers.Serializer):
    """Serializer for health metrics"""

    battery_level = serializers.IntegerField(required=False, min_value=0, max_value=100, allow_null=True)
    is_charging = serializers.BooleanField(default=False)
    storage_available_mb = serializers.IntegerField(required=False, min_value=0, allow_null=True)
    camera_active = serializers.BooleanField(default=False)
    network_type = serializers.CharField(required=False, max_length=20, allow_null=True)
    app_version = serializers.CharField(required=False, max_length=20, allow_null=True)
    last_face_detected_ago_min = serializers.IntegerField(required=False, min_value=0, allow_null=True)
    faces_detected_today = serializers.IntegerField(default=0, min_value=0)
    students_identified_today = serializers.IntegerField(default=0, min_value=0)


class HeartbeatSerializer(serializers.Serializer):
    """Serializer for kiosk heartbeat"""

    timestamp = serializers.DateTimeField(help_text="Heartbeat timestamp")
    database_version = serializers.CharField(max_length=50, help_text="Current database version on kiosk")
    database_hash = serializers.CharField(
        max_length=64,
        required=False,
        allow_blank=True,
        help_text="Database content hash",
    )
    student_count = serializers.IntegerField(min_value=0, help_text="Students in DB")
    embedding_count = serializers.IntegerField(min_value=0, help_text="Embeddings in DB")
    git_commit_sha = serializers.CharField(
        max_length=40,
        required=False,
        allow_null=True,
        help_text="Git commit SHA of the kiosk app build (40 chars). Null for dev builds.",
    )
    health = HealthDataSerializer(required=False)


class KioskStatusSerializer(serializers.ModelSerializer):
    """Serializer for KioskStatus model"""

    kiosk_id = serializers.CharField(source="kiosk.kiosk_id", read_only=True)
    bus_id = serializers.UUIDField(source="kiosk.bus.bus_id", read_only=True, allow_null=True)
    is_outdated = serializers.ReadOnlyField()
    is_offline = serializers.ReadOnlyField()

    class Meta:
        model = KioskStatus
        fields = [
            "kiosk_id",
            "bus_id",
            "last_heartbeat",
            "database_version",
            "database_hash",
            "student_count",
            "embedding_count",
            "battery_level",
            "is_charging",
            "storage_available_mb",
            "camera_active",
            "network_type",
            "app_version",
            "last_face_detected",
            "faces_detected_today",
            "students_identified_today",
            "status",
            "last_error",
            "is_outdated",
            "is_offline",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]


class BusLocationSerializer(serializers.ModelSerializer):
    """Serializer for GPS location updates from kiosk"""

    class Meta:
        model = BusLocation
        fields = [
            "location_id",
            "latitude",
            "longitude",
            "accuracy",
            "speed",
            "heading",
            "timestamp",
        ]
        read_only_fields = ["location_id"]

    def validate_latitude(self, value):
        """Validate latitude is valid"""
        if not (-90 <= value <= 90):
            raise serializers.ValidationError("Latitude must be between -90 and 90")
        return value

    def validate_longitude(self, value):
        """Validate longitude is valid"""
        if not (-180 <= value <= 180):
            raise serializers.ValidationError("Longitude must be between -180 and 180")
        return value


class SOSAlertSerializer(serializers.ModelSerializer):
    """Serializer for SOS emergency alerts"""

    kiosk_id = serializers.CharField(source="kiosk.kiosk_id", read_only=True)
    bus_license_plate = serializers.CharField(source="kiosk.bus.license_plate", read_only=True, allow_null=True)
    bus_number = serializers.CharField(source="kiosk.bus.bus_number", read_only=True, allow_null=True)

    class Meta:
        model = SOSAlert
        fields = [
            "alert_id",
            "kiosk_id",
            "bus_license_plate",
            "bus_number",
            "latitude",
            "longitude",
            "status",
            "message",
            "metadata",
            "created_at",
            "acknowledged_at",
            "resolved_at",
            "acknowledged_by",
            "resolved_by",
        ]
        read_only_fields = [
            "alert_id",
            "created_at",
            "acknowledged_at",
            "resolved_at",
        ]

    def validate_latitude(self, value):
        """Validate latitude is valid"""
        if value is not None and not (-90 <= value <= 90):
            raise serializers.ValidationError("Latitude must be between -90 and 90")
        return value

    def validate_longitude(self, value):
        """Validate longitude is valid"""
        if value is not None and not (-180 <= value <= 180):
            raise serializers.ValidationError("Longitude must be between -180 and 180")
        return value


class SOSAlertCreateSerializer(serializers.Serializer):
    """Serializer for creating SOS alerts from kiosk"""

    latitude = serializers.FloatField(required=False, allow_null=True, help_text="GPS latitude at time of alert")
    longitude = serializers.FloatField(required=False, allow_null=True, help_text="GPS longitude at time of alert")
    message = serializers.CharField(required=False, allow_blank=True, help_text="Optional message from operator")
    metadata = serializers.JSONField(required=False, default=dict, help_text="Additional context data")

    def validate_latitude(self, value):
        """Validate latitude is valid"""
        if value is not None and not (-90 <= value <= 90):
            raise serializers.ValidationError("Latitude must be between -90 and 90")
        return value

    def validate_longitude(self, value):
        """Validate longitude is valid"""
        if value is not None and not (-180 <= value <= 180):
            raise serializers.ValidationError("Longitude must be between -180 and 180")
        return value
