from typing import Any
import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
import ulid

from students.models import Student

# Configuration: Number of confirmation face photos
# Adjust this to change how many photos are stored (1-5 recommended)
# If changed, also update database migration to add/remove fields
MAX_CONFIRMATION_FACES = 3


class BoardingEvent(models.Model):
    """
    Boarding event model - append-only, never delete.
    Partitioned monthly by timestamp for performance.
    Uses ULID for globally unique, time-sortable IDs.
    """

    event_id = models.CharField(
        max_length=26,
        primary_key=True,
        editable=False,
        help_text="ULID primary key for global uniqueness and time sorting",
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="boarding_events",
        help_text="Student who boarded the bus",
    )
    kiosk_id = models.CharField(max_length=100, help_text="Kiosk device identifier")
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Face recognition confidence score (0.0-1.0)",
    )
    timestamp = models.DateTimeField(help_text="When the boarding event occurred")
    # GPS coordinates as latitude/longitude (will be converted to PostGIS POINT later)
    latitude = models.FloatField(null=True, blank=True, help_text="GPS latitude coordinate")
    longitude = models.FloatField(null=True, blank=True, help_text="GPS longitude coordinate")
    bus_route = models.CharField(max_length=100, blank=True, help_text="Bus route identifier")
    face_image_url = models.TextField(blank=True, help_text="S3 URL to face image for verification (optional)")
    model_version = models.CharField(max_length=50, help_text="Face recognition model version used")
    metadata = models.JSONField(default=dict, help_text="Additional metadata as JSON")
    created_at = models.DateTimeField(auto_now_add=True, help_text="When this record was created in database")

    # Confirmation face images (cropped 112x112 JPEG from kiosk)
    # These are the 3 consecutive frames that confirmed the student identification
    # Stored in Google Cloud Storage for better scalability and performance
    # Path format: boarding_events/{event_id}/face_{1,2,3}.jpg
    confirmation_face_1_gcs = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="GCS path for first confirmation face (112x112 JPEG, ~5-10KB)",
    )
    confirmation_face_2_gcs = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="GCS path for second confirmation face (112x112 JPEG, ~5-10KB)",
    )
    confirmation_face_3_gcs = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="GCS path for third confirmation face (112x112 JPEG, ~5-10KB)",
    )

    class Meta:
        db_table = "boarding_events"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["student", "timestamp"], name="idx_events_student_time"),
            models.Index(fields=["kiosk_id", "timestamp"], name="idx_events_kiosk_time"),
            models.Index(fields=["timestamp"], name="idx_events_timestamp"),
            # GPS index will be added when PostGIS is available
        ]
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(confidence_score__gte=0.0) & models.Q(confidence_score__lte=1.0)),
                name="chk_confidence_score_range",
            ),
        ]
        # Note: Monthly partitioning by timestamp would be implemented in PostgreSQL migration
        # Partitioning is not directly supported in Django ORM, requires raw SQL in migrations

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Generate ULID if not provided"""
        if not self.event_id:
            self.event_id = str(ulid.new())
        super().save(*args, **kwargs)

    @property
    def gps_coords(self) -> tuple[float, float] | None:
        """Return GPS coordinates as a tuple for compatibility"""
        if self.latitude is not None and self.longitude is not None:
            return (self.latitude, self.longitude)
        return None

    @property
    def confirmation_face_1_url(self) -> str | None:
        """Get signed GCS URL for first confirmation face (cached).

        Uses Redis cache to avoid regenerating URLs on every request.
        Cache duration: 55 minutes (matches signed URL expiration).

        Returns:
            Signed GCS URL (1-hour expiration) or None if no face image exists.
        """
        if not self.confirmation_face_1_gcs:
            return None

        import logging

        from django.core.cache import cache

        from .services.storage_service import BoardingEventStorageService

        logger = logging.getLogger(__name__)

        # Try to get cached URL first (Google best practice: cache signed URLs)
        cache_key = f"boarding_event_face_{self.event_id}_1"
        cached_url = cache.get(cache_key)

        if cached_url:
            logger.debug(f"Using cached signed URL for {self.event_id} face 1")
            return cached_url

        # Generate new signed URL if not cached
        try:
            storage_service = BoardingEventStorageService()
            url = storage_service.get_signed_url(self.confirmation_face_1_gcs)

            # Cache URL for 55 minutes (slightly less than 60-min expiration for safety)
            cache.set(cache_key, url, timeout=55 * 60)

            logger.info(f"Generated and cached signed URL for {self.event_id} face 1: SUCCESS")
            return url
        except Exception as e:
            logger.error(f"Failed to generate signed URL for {self.event_id} face 1: {e}", exc_info=True)
            return None

    @property
    def confirmation_face_2_url(self) -> str | None:
        """Get signed GCS URL for second confirmation face (cached).

        Uses Redis cache to avoid regenerating URLs on every request.
        Cache duration: 55 minutes (matches signed URL expiration).

        Returns:
            Signed GCS URL (1-hour expiration) or None if no face image exists.
        """
        if not self.confirmation_face_2_gcs:
            return None

        import logging

        from django.core.cache import cache

        from .services.storage_service import BoardingEventStorageService

        logger = logging.getLogger(__name__)

        # Try to get cached URL first (Google best practice: cache signed URLs)
        cache_key = f"boarding_event_face_{self.event_id}_2"
        cached_url = cache.get(cache_key)

        if cached_url:
            logger.debug(f"Using cached signed URL for {self.event_id} face 2")
            return cached_url

        # Generate new signed URL if not cached
        try:
            storage_service = BoardingEventStorageService()
            url = storage_service.get_signed_url(self.confirmation_face_2_gcs)

            # Cache URL for 55 minutes (slightly less than 60-min expiration for safety)
            cache.set(cache_key, url, timeout=55 * 60)

            logger.info(f"Generated and cached signed URL for {self.event_id} face 2: SUCCESS")
            return url
        except Exception as e:
            logger.error(f"Failed to generate signed URL for {self.event_id} face 2: {e}", exc_info=True)
            return None

    @property
    def confirmation_face_3_url(self) -> str | None:
        """Get signed GCS URL for third confirmation face (cached).

        Uses Redis cache to avoid regenerating URLs on every request.
        Cache duration: 55 minutes (matches signed URL expiration).

        Returns:
            Signed GCS URL (1-hour expiration) or None if no face image exists.
        """
        if not self.confirmation_face_3_gcs:
            return None

        import logging

        from django.core.cache import cache

        from .services.storage_service import BoardingEventStorageService

        logger = logging.getLogger(__name__)

        # Try to get cached URL first (Google best practice: cache signed URLs)
        cache_key = f"boarding_event_face_{self.event_id}_3"
        cached_url = cache.get(cache_key)

        if cached_url:
            logger.debug(f"Using cached signed URL for {self.event_id} face 3")
            return cached_url

        # Generate new signed URL if not cached
        try:
            storage_service = BoardingEventStorageService()
            url = storage_service.get_signed_url(self.confirmation_face_3_gcs)

            # Cache URL for 55 minutes (slightly less than 60-min expiration for safety)
            cache.set(cache_key, url, timeout=55 * 60)

            logger.info(f"Generated and cached signed URL for {self.event_id} face 3: SUCCESS")
            return url
        except Exception as e:
            logger.error(f"Failed to generate signed URL for {self.event_id} face 3: {e}", exc_info=True)
            return None

    def __str__(self) -> str:
        return f"BoardingEvent({self.event_id[:8]}...): {self.student} at {self.timestamp}"


class AttendanceRecord(models.Model):
    """
    Daily attendance record derived from boarding events.
    Updated daily by background job.
    """

    STATUS_CHOICES = [
        ("present", "Present"),
        ("absent", "Absent"),
        ("partial", "Partial"),
    ]

    record_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="UUID primary key",
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="attendance_records",
        help_text="Student attendance record",
    )
    date = models.DateField(help_text="Date of attendance record")
    morning_boarded = models.BooleanField(default=False, help_text="Whether student boarded in the morning")
    morning_time = models.DateTimeField(null=True, blank=True, help_text="Time of morning boarding")
    afternoon_boarded = models.BooleanField(default=False, help_text="Whether student boarded in the afternoon")
    afternoon_time = models.DateTimeField(null=True, blank=True, help_text="Time of afternoon boarding")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, help_text="Overall attendance status")
    created_at = models.DateTimeField(auto_now_add=True, help_text="When this record was created")

    class Meta:
        db_table = "attendance_records"
        ordering = ["-date"]
        unique_together = [["student", "date"]]
        indexes = [
            models.Index(fields=["student", "date"], name="idx_attendance_student_date"),
            models.Index(fields=["date"], name="idx_attendance_date"),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Auto-calculate status based on boarding times"""
        if self.morning_boarded and self.afternoon_boarded:
            self.status = "present"
        elif not self.morning_boarded and not self.afternoon_boarded:
            self.status = "absent"
        else:
            self.status = "partial"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Attendance({self.student} on {self.date}): {self.status}"
