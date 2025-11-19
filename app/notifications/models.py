from django.db import models
from django.utils import timezone
import ulid


def generate_ulid():
    """Generate a ULID string for notification IDs."""
    return str(ulid.new())


class FCMToken(models.Model):
    """
    Store FCM tokens for parent devices.
    A parent can have multiple tokens (multiple devices).
    """

    id = models.AutoField(primary_key=True)
    parent = models.ForeignKey("students.Parent", on_delete=models.CASCADE, related_name="fcm_tokens")
    token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(
        max_length=20,
        choices=[
            ("android", "Android"),
            ("ios", "iOS"),
            ("web", "Web"),
        ],
        default="android",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notifications_fcm_token"
        verbose_name = "FCM Token"
        verbose_name_plural = "FCM Tokens"
        indexes = [
            models.Index(fields=["parent", "is_active"]),
        ]

    def __str__(self):
        return f"{self.parent.parent_id} - {self.platform} ({self.token[:20]}...)"


class NotificationPreference(models.Model):
    """
    Store notification preferences for each parent.
    Controls which notification types the parent wants to receive.
    """

    id = models.AutoField(primary_key=True)
    parent = models.OneToOneField("students.Parent", on_delete=models.CASCADE, related_name="notification_preferences")

    # Notification type toggles
    boarding = models.BooleanField(default=True, help_text="Notify when child boards bus")
    deboarding = models.BooleanField(default=True, help_text="Notify when child drops off")
    eta = models.BooleanField(default=True, help_text="Notify about bus ETA")
    pickup_reminder = models.BooleanField(default=True, help_text="Remind before pickup")
    drop_reminder = models.BooleanField(default=True, help_text="Remind before drop-off")
    announcements = models.BooleanField(default=True, help_text="School announcements")

    # Quiet hours
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notifications_preference"
        verbose_name = "Notification Preference"
        verbose_name_plural = "Notification Preferences"

    def __str__(self):
        return f"Preferences for {self.parent.parent_id}"

    def is_type_enabled(self, notification_type: str) -> bool:
        """Check if a notification type is enabled."""
        type_map = {
            "boarding": self.boarding,
            "deboarding": self.deboarding,
            "eta": self.eta,
            "pickup_reminder": self.pickup_reminder,
            "drop_reminder": self.drop_reminder,
            "announcements": self.announcements,
        }
        return type_map.get(notification_type, True)


class Notification(models.Model):
    """
    Store all notifications with their delivery status.
    Acts as a queue and audit trail.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("queued", "Queued"),
        ("sent", "Sent"),
        ("failed", "Failed"),
        ("read", "Read"),
    ]

    TYPE_CHOICES = [
        ("boarding", "Boarding"),
        ("deboarding", "Deboarding"),
        ("eta", "ETA"),
        ("pickup_reminder", "Pickup Reminder"),
        ("drop_reminder", "Drop Reminder"),
        ("announcement", "Announcement"),
    ]

    notification_id = models.CharField(max_length=26, primary_key=True, default=generate_ulid)
    parent = models.ForeignKey("students.Parent", on_delete=models.CASCADE, related_name="notifications")
    student = models.ForeignKey("students.Student", on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications")

    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=255)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Tracking
    retry_count = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    queued_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications_notification"
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["parent", "status"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["notification_type"]),
        ]

    def __str__(self):
        return f"{self.notification_type}: {self.title[:50]}"

    def mark_as_queued(self):
        """Mark notification as queued for delivery."""
        self.status = "queued"
        self.queued_at = timezone.now()
        self.save(update_fields=["status", "queued_at"])

    def mark_as_sent(self):
        """Mark notification as successfully sent."""
        self.status = "sent"
        self.sent_at = timezone.now()
        self.save(update_fields=["status", "sent_at"])

    def mark_as_failed(self, error_message: str):
        """Mark notification as failed with error message."""
        self.status = "failed"
        self.error_message = error_message
        self.retry_count += 1
        self.save(update_fields=["status", "error_message", "retry_count"])

    def mark_as_read(self):
        """Mark notification as read by parent."""
        self.status = "read"
        self.read_at = timezone.now()
        self.save(update_fields=["status", "read_at"])
