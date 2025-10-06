from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from buses.models import Bus


class Kiosk(models.Model):
    """
    Kiosk device model for bus-mounted face recognition devices.
    Each kiosk has a unique API key for authentication.
    """

    kiosk_id = models.CharField(
        max_length=100,
        primary_key=True,
        help_text="Unique kiosk device identifier (e.g., KIOSK001, BUS123-KIOSK)",
    )
    bus = models.OneToOneField(
        Bus,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kiosk",
        help_text="Bus this kiosk is installed on",
    )
    api_key_hash = models.CharField(
        max_length=255,
        unique=True,
        help_text="Hashed API key for device authentication",
    )
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
        default=True, help_text="Whether this kiosk is active and accepting requests"
    )
    battery_level = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Battery level percentage (0-100)",
    )
    storage_used_mb = models.PositiveIntegerField(
        null=True, blank=True, help_text="Storage used in MB on the device"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When this kiosk was registered"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="When this kiosk record was last updated"
    )

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
    last_heartbeat = models.DateTimeField(
        help_text="Last heartbeat received from kiosk"
    )
    database_version = models.CharField(
        max_length=50, help_text="Timestamp of current database version"
    )
    database_hash = models.CharField(
        max_length=32,
        blank=True,
        help_text="Content hash of kiosk database (for integrity)",
    )
    student_count = models.IntegerField(
        default=0, help_text="Number of students in kiosk database"
    )
    embedding_count = models.IntegerField(
        default=0, help_text="Number of embeddings in kiosk database"
    )

    # Health metrics
    battery_level = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Battery level percentage (0-100)",
    )
    is_charging = models.BooleanField(default=False, help_text="Is device charging")
    storage_available_mb = models.IntegerField(
        null=True, blank=True, help_text="Available storage in MB"
    )
    camera_active = models.BooleanField(
        default=False, help_text="Is camera currently active"
    )
    network_type = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Network type (wifi, 4g, none)",
    )
    app_version = models.CharField(
        max_length=20, null=True, blank=True, help_text="Kiosk app version"
    )

    # Activity stats
    last_face_detected = models.DateTimeField(
        null=True, blank=True, help_text="Last time a face was detected"
    )
    faces_detected_today = models.IntegerField(
        default=0, help_text="Faces detected today"
    )
    students_identified_today = models.IntegerField(
        default=0, help_text="Students identified today"
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="ok",
        help_text="Overall kiosk status",
    )
    last_error = models.TextField(
        null=True, blank=True, help_text="Last error message if any"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="When this status was last updated"
    )

    class Meta:
        db_table = "kiosk_status"
        verbose_name = "Kiosk Status"
        verbose_name_plural = "Kiosk Statuses"
        indexes = [
            models.Index(fields=["status"], name="idx_kiosk_status_status"),
            models.Index(
                fields=["last_heartbeat"], name="idx_kiosk_status_heartbeat"
            ),
        ]

    def __str__(self):
        return f"{self.kiosk.kiosk_id} - {self.get_status_display()}"

    @property
    def is_outdated(self):
        """Check if kiosk database is outdated compared to bus"""
        if not self.kiosk.bus:
            return False

        return (
            self.kiosk.bus.last_student_update.isoformat()
            > self.database_version
        )

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

    log_id = models.BigAutoField(
        primary_key=True, help_text="Auto-incrementing log entry ID"
    )
    kiosk = models.ForeignKey(
        Kiosk,
        on_delete=models.CASCADE,
        related_name="logs",
        help_text="Kiosk that generated this log entry",
    )
    log_level = models.CharField(
        max_length=20, choices=LOG_LEVELS, help_text="Log level severity"
    )
    message = models.TextField(help_text="Log message content")
    metadata = models.JSONField(
        default=dict, blank=True, help_text="Additional structured data as JSON"
    )
    timestamp = models.DateTimeField(
        default=timezone.now, help_text="When this log entry was created"
    )

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
        return (
            f"[{self.timestamp}] {self.kiosk.kiosk_id} {self.log_level}: "
            f"{self.message[:50]}..."
        )

    @classmethod
    def log(cls, kiosk, level, message, metadata=None, timestamp=None):
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
