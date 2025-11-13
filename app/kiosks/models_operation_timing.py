"""Operation timing models for kiosk schedules"""
from django.db import models


class OperationTiming(models.Model):
    """
    Reusable operation timing schedules for kiosks.
    Define once, use for multiple kiosks.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Schedule name (e.g., 'Morning Shift', 'Full Day')",
    )
    description = models.TextField(
        blank=True,
        help_text="Optional description of this schedule",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this schedule is available for selection",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "operation_timings"
        ordering = ["name"]
        verbose_name = "Operation Timing"
        verbose_name_plural = "Operation Timings"

    def __str__(self):
        return self.name


class OperationSlot(models.Model):
    """
    Time slots for operation timing.
    Each timing can have multiple slots (e.g., morning + afternoon).
    """

    timing = models.ForeignKey(
        OperationTiming,
        on_delete=models.CASCADE,
        related_name="slots",
        help_text="Operation timing this slot belongs to",
    )
    start_time = models.TimeField(help_text="Start time (e.g., 08:00)")
    end_time = models.TimeField(help_text="End time (e.g., 10:00)")
    order = models.IntegerField(
        default=0,
        help_text="Display order (0 = first slot)",
    )

    class Meta:
        db_table = "operation_slots"
        ordering = ["timing", "order", "start_time"]
        verbose_name = "Operation Slot"
        verbose_name_plural = "Operation Slots"

    def __str__(self):
        return f"{self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"
