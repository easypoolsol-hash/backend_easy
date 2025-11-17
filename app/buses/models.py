import uuid

from django.core.validators import MinValueValidator
from django.db import models

from students.models import Student


class BusStop(models.Model):
    """Physical bus stop location where students board/alight"""

    stop_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="UUID primary key",
    )
    name = models.CharField(
        max_length=200,
        help_text="Stop name (e.g., 'Main Gate', 'North Entrance')",
    )
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        help_text="Latitude coordinate",
    )
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        help_text="Longitude coordinate",
    )
    is_active = models.BooleanField(default=True, help_text="Whether this stop is currently active")
    created_at = models.DateTimeField(auto_now_add=True, help_text="When this stop was created")
    updated_at = models.DateTimeField(auto_now=True, help_text="When this stop was last updated")

    class Meta:
        db_table = "bus_stops"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active"], name="idx_stops_active"),
            models.Index(fields=["latitude", "longitude"], name="idx_stops_coords"),
        ]

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"


class Route(models.Model):
    """Bus route composed of ordered bus stops"""

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
    description = models.TextField(blank=True, help_text="Detailed description of the route")
    color_code = models.CharField(
        max_length=7,
        default="#0072B2",
        help_text="Hex color for map display (e.g., #FF5733)",
    )
    line_pattern = models.CharField(
        max_length=20,
        choices=[
            ("solid", "Solid Line"),
            ("dashed", "Dashed Line"),
        ],
        default="solid",
        help_text="Line pattern for map visualization",
    )
    encoded_polyline = models.TextField(
        blank=True,
        help_text="Google-encoded polyline for the entire route path",
    )
    is_active = models.BooleanField(default=True, help_text="Whether this route is currently active")
    created_at = models.DateTimeField(auto_now_add=True, help_text="When this route was created")
    updated_at = models.DateTimeField(auto_now=True, help_text="When this route was last updated")

    class Meta:
        db_table = "routes"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active"], name="idx_routes_active"),
        ]

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"

    def save(self, *args, **kwargs):
        """Auto-generate encoded polyline from waypoints on save"""
        # Save first to ensure we have a primary key for relationships
        super().save(*args, **kwargs)

        # Auto-generate polyline if route has waypoints
        if not self.encoded_polyline or kwargs.get("force_regenerate_polyline", False):
            self.regenerate_polyline()

    def regenerate_polyline(self):
        """Generate encoded polyline from route waypoints"""
        from buses.utils.polyline_generator import PolylineGenerationError, generate_route_polyline

        # Get all waypoints in sequence order
        waypoints_qs = self.route_waypoints.select_related("waypoint").order_by("sequence")

        if waypoints_qs.count() < 2:
            # Need at least 2 points for a route
            return

        try:
            # Extract (lat, lng) tuples
            coords = [(float(rw.waypoint.latitude), float(rw.waypoint.longitude)) for rw in waypoints_qs]

            # Generate polyline using Google Directions API
            polyline = generate_route_polyline(coords)

            # Update without triggering save recursion
            Route.objects.filter(pk=self.pk).update(encoded_polyline=polyline)

            # Update instance
            self.encoded_polyline = polyline

        except PolylineGenerationError as e:
            # Log but don't fail the save
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to generate polyline for route {self.name}: {e}")

    @property
    def stop_count(self):
        """Return the number of stops in this route"""
        return self.route_stops.count()

    @property
    def total_students(self):
        """Return total students assigned to buses on this route"""
        return Student.objects.filter(assigned_bus__route=self, status="active").count()


class RouteStop(models.Model):
    """Junction table linking routes to stops with sequence and waypoints"""

    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name="route_stops",
        help_text="Route this stop belongs to",
    )
    bus_stop = models.ForeignKey(
        BusStop,
        on_delete=models.CASCADE,
        related_name="route_stops",
        help_text="Bus stop on this route",
    )
    sequence = models.PositiveIntegerField(help_text="Order of this stop in the route (1-based)")
    waypoints = models.JSONField(
        default=list,
        blank=True,
        help_text="Path coordinates to NEXT stop: [{lat, lon}, ...]",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "route_stops"
        ordering = ["route", "sequence"]
        unique_together = [["route", "bus_stop"], ["route", "sequence"]]
        indexes = [
            models.Index(fields=["route", "sequence"], name="idx_routestop"),
        ]

    def __str__(self):
        return f"{self.route.name} - Stop {self.sequence}: {self.bus_stop.name}"


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
    bus_number = models.CharField(
        max_length=20,
        unique=True,
        help_text="School-assigned bus number (e.g., 'BUS-001', 'B-12')",
    )
    license_plate = models.CharField(max_length=20, unique=True, help_text="Vehicle license plate number")
    route = models.ForeignKey(
        Route,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="buses",
        help_text="Route this bus is assigned to",
    )
    capacity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        blank=True,
        null=True,
        help_text="Maximum number of passengers",
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
    manufacturer = models.CharField(max_length=100, blank=True, help_text="Bus manufacturer")
    model = models.CharField(max_length=100, blank=True, help_text="Bus model")
    year = models.PositiveIntegerField(null=True, blank=True, help_text="Manufacturing year")
    last_maintenance = models.DateField(null=True, blank=True, help_text="Date of last maintenance")

    # Driver information
    driver_name = models.CharField(max_length=200, blank=True, help_text="Driver's full name")
    driver_phone = models.CharField(max_length=20, blank=True, help_text="Driver's contact number")
    driver_address = models.TextField(blank=True, help_text="Driver's address")
    driver_license_number = models.CharField(max_length=50, blank=True, help_text="Driver's license number")

    # Conductor information
    conductor_name = models.CharField(max_length=200, blank=True, help_text="Conductor's full name")
    conductor_phone = models.CharField(max_length=20, blank=True, help_text="Conductor's contact number")
    conductor_address = models.TextField(blank=True, help_text="Conductor's address")
    created_at = models.DateTimeField(auto_now_add=True, help_text="When this bus was added to the system")
    updated_at = models.DateTimeField(auto_now=True, help_text="When this bus record was last updated")
    last_student_update = models.DateTimeField(
        auto_now=True,
        help_text="Last time students/embeddings changed for this bus",
    )

    class Meta:
        db_table = "buses"
        ordering = ["bus_number"]
        indexes = [
            models.Index(fields=["route", "status"], name="idx_buses_route_status"),
            models.Index(fields=["device_id"], name="idx_buses_device"),
            models.Index(fields=["license_plate"], name="idx_buses_license"),
            models.Index(fields=["bus_number"], name="idx_buses_number"),
            models.Index(fields=["status"], name="idx_buses_status"),
        ]

    def __str__(self):
        return f"Bus {self.bus_number} - {self.license_plate} ({self.get_status_display()})"

    @property
    def assigned_students_count(self):
        """Return number of students assigned to this bus"""
        return Student.objects.filter(assigned_bus=self, status="active").count()

    @property
    def utilization_percentage(self):
        """Return bus utilization as percentage"""
        if self.capacity is not None and self.capacity > 0:
            return (self.assigned_students_count / self.capacity) * 100
        return 0

    @property
    def is_available(self):
        """Check if bus is available for operation"""
        return self.status == "active" and self.route is not None


class Waypoint(models.Model):
    """
    Waypoint model for route path definition.
    Can be a bus stop or a path adjustment point.
    """

    waypoint_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="UUID primary key",
    )
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        help_text="Latitude coordinate",
    )
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        help_text="Longitude coordinate",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Flexible metadata: {type: 'bus_stop'/'path_adjustment', name: '...', ...}",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "waypoints"
        indexes = [
            models.Index(fields=["latitude", "longitude"], name="idx_waypoints_coords"),
        ]

    def __str__(self):
        waypoint_type = self.metadata.get("type", "waypoint")
        name = self.metadata.get("name", f"Waypoint {str(self.waypoint_id)[:8]}")
        return f"{name} ({waypoint_type})"

    @property
    def is_bus_stop(self):
        """Check if this waypoint is a bus stop"""
        return self.metadata.get("type") == "bus_stop"


class RouteWaypoint(models.Model):
    """Junction table linking routes to waypoints with sequence"""

    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name="route_waypoints",
        help_text="Route this waypoint belongs to",
    )
    waypoint = models.ForeignKey(
        Waypoint,
        on_delete=models.CASCADE,
        related_name="routes",
        help_text="Waypoint on this route",
    )
    sequence = models.PositiveIntegerField(help_text="Order of this waypoint in the route (1-based)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "route_waypoints"
        ordering = ["route", "sequence"]
        unique_together = [["route", "sequence"]]  # Only sequence must be unique, same waypoint can appear multiple times
        indexes = [
            models.Index(fields=["route", "sequence"], name="idx_route_waypoints"),
        ]

    def __str__(self):
        return f"{self.route.name} - Seq {self.sequence}: {self.waypoint}"

    def save(self, *args, **kwargs):
        """Trigger polyline regeneration when waypoints change"""
        super().save(*args, **kwargs)
        # Regenerate route polyline whenever waypoints change
        self.route.regenerate_polyline()

    def delete(self, *args, **kwargs):
        """Trigger polyline regeneration when waypoints are deleted"""
        route = self.route
        super().delete(*args, **kwargs)
        # Regenerate route polyline after deletion
        route.regenerate_polyline()
