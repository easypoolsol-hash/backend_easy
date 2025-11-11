from __future__ import annotations

from datetime import datetime
from typing import Any

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from buses.models import Bus


class Kiosk(models.Model):
    """
    Kiosk device model for bus-mounted face recognition devices.

    Security: No stored credentials - uses one-time activation tokens only.
    """

    kiosk_id = models.CharField(
        max_length=100,
        primary_key=True,
        help_text="Unique kiosk device identifier (e.g., KIOSK001, BUS123-KIOSK)",
    )
    firebase_uid = models.CharField(
        max_length=128,
        unique=True,
        null=True,
        blank=True,
        help_text="Firebase UID for this kiosk user (from Firebase Authentication)",
    )
    bus = models.OneToOneField(
        Bus,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kiosk",
        help_text="Bus this kiosk is installed on",
    )
    # REMOVED: api_key_hash - we use activation tokens instead (more secure)
    firmware_version = models.CharField(
        max_length=50,
        blank=True,
        help_text="Current firmware version installed on device",
    )
    last_heartbeat = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last heartbeat received from device",
    )
    is_active = models.BooleanField(
        default=False,  # Changed from True - kiosks start inactive until activated
        help_text="Whether this kiosk is active and accepting requests",
    )
    battery_level = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Battery level percentage (0-100)",
    )
    storage_used_mb = models.PositiveIntegerField(null=True, blank=True, help_text="Storage used in MB on the device")
    created_at = models.DateTimeField(auto_now_add=True, help_text="When this kiosk was registered")
    updated_at = models.DateTimeField(auto_now=True, help_text="When this kiosk record was last updated")

    class Meta:
        db_table = "kiosks"
        ordering = ["kiosk_id"]
        indexes = [
            models.Index(fields=["bus"], name="idx_kiosk_bus"),
            models.Index(fields=["last_heartbeat"], name="idx_kiosk_heartbeat"),
            models.Index(fields=["is_active"], name="idx_kiosk_active"),
        ]

    def __str__(self):
        bus_info = f" on {self.bus.license_plate}" if self.bus else " (unassigned)"
        return f"{self.kiosk_id}{bus_info}"

    @property
    def is_online(self):
        """Check if kiosk is online based on heartbeat"""
        if not self.last_heartbeat:
            return False

        from datetime import timedelta

        from django.utils import timezone

        # Consider online if heartbeat within last 5 minutes
        return self.last_heartbeat > timezone.now() - timedelta(minutes=5)

    @property
    def is_authenticated(self):
        """
        DRF compatibility: Always True for kiosk objects.

        This property allows Kiosk to be used as request.user in DRF views.
        If a Kiosk object exists as request.user, it means authentication succeeded.

        Fortune 500 pattern: Makes Kiosk work with IsAuthenticated permission.
        """
        return True

    @property
    def status_display(self):
        """Human-readable status"""
        if not self.is_active:
            return "Inactive"
        elif self.is_online:
            return "Online"
        else:
            return "Offline"

    def update_heartbeat(self):
        """Update the last heartbeat timestamp"""
        from django.utils import timezone

        self.last_heartbeat = timezone.now()
        self.save(update_fields=["last_heartbeat", "updated_at"])


class KioskStatus(models.Model):
    """
    Sync and health status for each kiosk.
    Updated via heartbeat API.
    """

    STATUS_CHOICES = [
        ("ok", "OK"),
        ("warning", "Warning"),
        ("critical", "Critical"),
    ]

    kiosk = models.OneToOneField(
        Kiosk,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="status",
        help_text="Kiosk this status belongs to",
    )
    last_heartbeat = models.DateTimeField(help_text="Last heartbeat received from kiosk")
    database_version = models.CharField(max_length=50, help_text="Timestamp of current database version")
    database_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 hash of kiosk database content (for integrity)",
    )
    student_count = models.IntegerField(default=0, help_text="Number of students in kiosk database")
    embedding_count = models.IntegerField(default=0, help_text="Number of embeddings in kiosk database")

    # Health metrics
    battery_level = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Battery level percentage (0-100)",
    )
    is_charging = models.BooleanField(default=False, help_text="Is device charging")
    storage_available_mb = models.IntegerField(null=True, blank=True, help_text="Available storage in MB")
    camera_active = models.BooleanField(default=False, help_text="Is camera currently active")
    network_type = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Network type (wifi, 4g, none)",
    )
    app_version = models.CharField(max_length=20, null=True, blank=True, help_text="Kiosk app version")

    # Activity stats
    last_face_detected = models.DateTimeField(null=True, blank=True, help_text="Last time a face was detected")
    faces_detected_today = models.IntegerField(default=0, help_text="Faces detected today")
    students_identified_today = models.IntegerField(default=0, help_text="Students identified today")

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="ok",
        help_text="Overall kiosk status",
    )
    last_error = models.TextField(null=True, blank=True, help_text="Last error message if any")
    updated_at = models.DateTimeField(auto_now=True, help_text="When this status was last updated")

    class Meta:
        db_table = "kiosk_status"
        verbose_name = "Kiosk Status"
        verbose_name_plural = "Kiosk Statuses"
        indexes = [
            models.Index(fields=["status"], name="idx_kiosk_status_status"),
            models.Index(fields=["last_heartbeat"], name="idx_kiosk_status_heartbeat"),
        ]

    def __str__(self):
        return f"{self.kiosk.kiosk_id} - {self.get_status_display()}"

    @property
    def is_outdated(self):
        """Check if kiosk database is outdated compared to bus"""
        if not self.kiosk.bus:
            return False

        return self.kiosk.bus.last_student_update.isoformat() > self.database_version

    @property
    def is_offline(self):
        """Check if kiosk is offline (no heartbeat in 24 hours)"""
        from datetime import timedelta

        from django.utils import timezone

        return self.last_heartbeat < timezone.now() - timedelta(hours=24)


class DeviceLog(models.Model):
    """
    Device log entries from kiosks.
    Partitioned monthly for performance.
    """

    LOG_LEVELS = [
        ("DEBUG", "Debug"),
        ("INFO", "Info"),
        ("WARN", "Warning"),
        ("ERROR", "Error"),
        ("CRITICAL", "Critical"),
    ]

    log_id = models.BigAutoField(primary_key=True, help_text="Auto-incrementing log entry ID")
    kiosk = models.ForeignKey(
        Kiosk,
        on_delete=models.CASCADE,
        related_name="logs",
        help_text="Kiosk that generated this log entry",
    )
    log_level = models.CharField(max_length=20, choices=LOG_LEVELS, help_text="Log level severity")
    message = models.TextField(help_text="Log message content")
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional structured data as JSON")
    timestamp = models.DateTimeField(default=timezone.now, help_text="When this log entry was created")

    class Meta:
        db_table = "device_logs"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["kiosk", "timestamp"], name="idx_logs_kiosk_time"),
            models.Index(fields=["log_level"], name="idx_logs_level"),
            models.Index(fields=["timestamp"], name="idx_logs_timestamp"),
        ]
        # Note: Monthly partitioning by timestamp would be implemented in
        # PostgreSQL migration. Partitioning is not directly supported in
        # Django ORM, requires raw SQL in migrations

    def __str__(self):
        return f"[{self.timestamp}] {self.kiosk.kiosk_id} {self.log_level}: {self.message[:50]}..."

    @classmethod
    def log(
        cls: type[DeviceLog],
        kiosk: Kiosk,
        level: str,
        message: str,
        metadata: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> DeviceLog:
        """Convenience method to create a log entry"""
        data = {
            "kiosk": kiosk,
            "log_level": level,
            "message": message,
            "metadata": metadata or {},
        }
        if timestamp is not None:
            data["timestamp"] = timestamp
        return cls.objects.create(**data)


class BusLocation(models.Model):
    """
    Continuous GPS location tracking for buses.

    Backend simply stores GPS updates sent by kiosk.
    Kiosk app decides when to send (based on distance/time thresholds).

    Independent of boarding events - pure location tracking.
    """

    location_id = models.BigAutoField(primary_key=True, help_text="Auto-incrementing location entry ID")

    kiosk = models.ForeignKey(Kiosk, on_delete=models.CASCADE, related_name="locations", help_text="Kiosk/bus that sent this location update")

    latitude = models.FloatField(help_text="GPS latitude coordinate")

    longitude = models.FloatField(help_text="GPS longitude coordinate")

    accuracy = models.FloatField(null=True, blank=True, help_text="GPS accuracy in meters")

    speed = models.FloatField(null=True, blank=True, help_text="Speed in km/h")

    heading = models.FloatField(null=True, blank=True, help_text="Heading/bearing in degrees (0-360)")

    timestamp = models.DateTimeField(help_text="When this location was recorded by the kiosk")

    created_at = models.DateTimeField(auto_now_add=True, help_text="When this location was received by the server")

    class Meta:
        db_table = "bus_locations"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["kiosk", "-timestamp"], name="idx_busloc_kiosk_time"),
            models.Index(fields=["-timestamp"], name="idx_busloc_timestamp"),
        ]

    def __str__(self):
        return f"{self.kiosk.kiosk_id} at ({self.latitude}, {self.longitude}) - {self.timestamp}"

    @property
    def coordinates(self):
        """Return coordinates as tuple (lat, lng)"""
        return (self.latitude, self.longitude)


class SOSAlert(models.Model):
    """
    Emergency SOS alerts triggered by kiosk drivers/attendants.

    Provides immediate emergency notification with location tracking.
    """

    ALERT_STATUS_CHOICES = [
        ("active", "Active"),
        ("acknowledged", "Acknowledged"),
        ("resolved", "Resolved"),
        ("false_alarm", "False Alarm"),
    ]

    alert_id = models.BigAutoField(primary_key=True, help_text="Auto-incrementing alert ID")

    kiosk = models.ForeignKey(Kiosk, on_delete=models.CASCADE, related_name="sos_alerts", help_text="Kiosk that triggered the SOS alert")

    latitude = models.FloatField(null=True, blank=True, help_text="GPS latitude at time of alert")
    longitude = models.FloatField(null=True, blank=True, help_text="GPS longitude at time of alert")

    status = models.CharField(max_length=20, choices=ALERT_STATUS_CHOICES, default="active", help_text="Current status of the alert")

    message = models.TextField(blank=True, help_text="Optional message/notes from the kiosk operator")

    metadata = models.JSONField(default=dict, blank=True, help_text="Additional data (battery level, network status, etc.)")

    created_at = models.DateTimeField(auto_now_add=True, help_text="When the alert was created")

    acknowledged_at = models.DateTimeField(null=True, blank=True, help_text="When the alert was first acknowledged by staff")

    resolved_at = models.DateTimeField(null=True, blank=True, help_text="When the alert was resolved")

    acknowledged_by = models.CharField(max_length=255, blank=True, help_text="Name/ID of person who acknowledged the alert")

    resolved_by = models.CharField(max_length=255, blank=True, help_text="Name/ID of person who resolved the alert")

    class Meta:
        db_table = "sos_alerts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["kiosk", "-created_at"], name="idx_sos_kiosk_time"),
            models.Index(fields=["status"], name="idx_sos_status"),
            models.Index(fields=["-created_at"], name="idx_sos_created"),
        ]

    def __str__(self):
        return f"SOS Alert #{self.alert_id} - {self.kiosk.kiosk_id} ({self.status}) - {self.created_at}"

    @property
    def coordinates(self):
        """Return coordinates as tuple (lat, lng)"""
        if self.latitude is not None and self.longitude is not None:
            return (self.latitude, self.longitude)
        return None

    @property
    def is_active(self):
        """Check if alert is still active"""
        return self.status == "active"
