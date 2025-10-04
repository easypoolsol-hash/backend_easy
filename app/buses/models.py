import uuid

from django.core.validators import MinValueValidator
from django.db import models

from students.models import Student


class Route(models.Model):
    """
    Bus route model with embedded stops and schedule information.
    """

    route_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="UUID primary key",
    )
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Route name (e.g., 'Route A', 'North Loop')",
    )
    description = models.TextField(
        blank=True, help_text="Detailed description of the route"
    )
    stops = models.JSONField(
        default=list,
        help_text="Array of stop objects: [{name, lat, lon, sequence, estimated_time}]",
    )
    schedule = models.JSONField(
        default=dict,
        help_text="Schedule data: {morning: {start, end}, afternoon: {start, end}}",
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this route is currently active"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When this route was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="When this route was last updated"
    )

    class Meta:
        db_table = "routes"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active"], name="idx_routes_active"),
        ]

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"

    @property
    def stop_count(self):
        """Return the number of stops in this route"""
        return len(self.stops) if self.stops else 0

    @property
    def total_students(self):
        """Return total number of students assigned to buses on this route"""
        return Student.objects.filter(assigned_bus__route=self, status="active").count()


class Bus(models.Model):
    """
    Bus model representing physical buses in the fleet.
    """

    STATUS_CHOICES = [
        ("active", "Active"),
        ("maintenance", "Under Maintenance"),
        ("retired", "Retired"),
    ]

    bus_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="UUID primary key",
    )
    license_plate = models.CharField(
        max_length=20, unique=True, help_text="Vehicle license plate number"
    )
    route = models.ForeignKey(
        Route,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="buses",
        help_text="Route this bus is assigned to",
    )
    capacity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)], help_text="Maximum number of passengers"
    )
    device_id = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        null=True,
        help_text="Kiosk device identifier installed on this bus",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        help_text="Current operational status",
    )
    manufacturer = models.CharField(
        max_length=100, blank=True, help_text="Bus manufacturer"
    )
    model = models.CharField(max_length=100, blank=True, help_text="Bus model")
    year = models.PositiveIntegerField(
        null=True, blank=True, help_text="Manufacturing year"
    )
    last_maintenance = models.DateField(
        null=True, blank=True, help_text="Date of last maintenance"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When this bus was added to the system"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="When this bus record was last updated"
    )

    class Meta:
        db_table = "buses"
        ordering = ["license_plate"]
        indexes = [
            models.Index(fields=["route", "status"], name="idx_buses_route_status"),
            models.Index(fields=["device_id"], name="idx_buses_device"),
            models.Index(fields=["license_plate"], name="idx_buses_license"),
            models.Index(fields=["status"], name="idx_buses_status"),
        ]

    def __str__(self):
        return f"{self.license_plate} ({self.get_status_display()})"

    @property
    def assigned_students_count(self):
        """Return number of students assigned to this bus"""
        return Student.objects.filter(assigned_bus=self, status="active").count()

    @property
    def utilization_percentage(self):
        """Return bus utilization as percentage"""
        if self.capacity > 0:
            return (self.assigned_students_count / self.capacity) * 100
        return 0

    @property
    def is_available(self):
        """Check if bus is available for operation"""
        return self.status == "active" and self.route is not None
