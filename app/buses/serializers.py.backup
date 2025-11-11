from drf_spectacular.utils import extend_schema_field
import polyline
from rest_framework import serializers

from .models import Bus, BusStop, Route, RouteStop, RouteWaypoint, Waypoint


class BusStopSerializer(serializers.ModelSerializer):
    """Serializer for bus stops"""

    class Meta:
        model = BusStop
        fields = [
            "stop_id",
            "name",
            "latitude",
            "longitude",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["stop_id", "created_at", "updated_at"]


class RouteStopSerializer(serializers.ModelSerializer):
    """Serializer for route stops with nested bus stop info"""

    bus_stop_name = serializers.CharField(source="bus_stop.name", read_only=True)
    latitude = serializers.FloatField(source="bus_stop.latitude", read_only=True)
    longitude = serializers.FloatField(source="bus_stop.longitude", read_only=True)

    class Meta:
        model = RouteStop
        fields = [
            "bus_stop",
            "bus_stop_name",
            "latitude",
            "longitude",
            "sequence",
            "waypoints",
        ]


class WaypointSerializer(serializers.ModelSerializer):
    """Serializer for waypoints"""

    class Meta:
        model = Waypoint
        fields = [
            "waypoint_id",
            "latitude",
            "longitude",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["waypoint_id", "created_at", "updated_at"]


class RouteWaypointSerializer(serializers.ModelSerializer):
    """Serializer for route waypoints with nested waypoint info"""

    latitude = serializers.FloatField(source="waypoint.latitude", read_only=True)
    longitude = serializers.FloatField(source="waypoint.longitude", read_only=True)
    metadata = serializers.JSONField(source="waypoint.metadata", read_only=True)

    class Meta:
        model = RouteWaypoint
        fields = [
            "sequence",
            "latitude",
            "longitude",
            "metadata",
        ]


class RouteSerializer(serializers.ModelSerializer):
    """Serializer for bus routes with polyline support"""

    stop_count = serializers.IntegerField(read_only=True)
    total_students = serializers.IntegerField(read_only=True)
    route_stops = RouteStopSerializer(many=True, read_only=True)

    # New waypoint-based fields
    encoded_polyline = serializers.SerializerMethodField()
    bus_stops = serializers.SerializerMethodField()

    class Meta:
        model = Route
        fields = [
            "route_id",
            "name",
            "description",
            "color_code",
            "line_pattern",
            "is_active",
            "stop_count",
            "total_students",
            "route_stops",
            "encoded_polyline",
            "bus_stops",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["route_id", "created_at", "updated_at"]

    @extend_schema_field(serializers.CharField(allow_blank=True))
    def get_encoded_polyline(self, obj) -> str:
        """Generate encoded polyline from route waypoints"""
        # Check if we have cached polyline
        if obj.encoded_polyline:
            return obj.encoded_polyline

        # Generate from waypoints if available
        waypoints = obj.route_waypoints.order_by("sequence")
        if not waypoints.exists():
            # Fallback to old route_stops
            route_stops = obj.route_stops.order_by("sequence")
            if route_stops.exists():
                coords = [(float(rs.bus_stop.latitude), float(rs.bus_stop.longitude)) for rs in route_stops]
                return polyline.encode(coords, 5)
        else:
            coords = [(float(rw.waypoint.latitude), float(rw.waypoint.longitude)) for rw in waypoints]
            return polyline.encode(coords, 5)

        return ""

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_bus_stops(self, obj) -> list:
        """Get only bus stop waypoints for markers"""
        bus_stops = []

        # Get from new waypoints
        waypoints = obj.route_waypoints.select_related("waypoint").order_by("sequence")
        for rw in waypoints:
            if rw.waypoint.metadata.get("type") == "bus_stop":
                bus_stops.append(
                    {
                        "latitude": float(rw.waypoint.latitude),
                        "longitude": float(rw.waypoint.longitude),
                        "sequence": rw.sequence,
                        "metadata": rw.waypoint.metadata,
                    }
                )

        # Fallback to old route_stops if no waypoints
        if not bus_stops:
            route_stops = obj.route_stops.select_related("bus_stop").order_by("sequence")
            for rs in route_stops:
                bus_stops.append(
                    {
                        "latitude": float(rs.bus_stop.latitude),
                        "longitude": float(rs.bus_stop.longitude),
                        "sequence": rs.sequence,
                        "metadata": {"type": "bus_stop", "name": rs.bus_stop.name},
                    }
                )

        return bus_stops


class BusSerializer(serializers.ModelSerializer):
    """Serializer for buses"""

    route_name = serializers.CharField(source="route.name", read_only=True)
    assigned_students_count = serializers.IntegerField(read_only=True)
    utilization_percentage = serializers.FloatField(read_only=True)
    is_available = serializers.BooleanField(read_only=True)

    class Meta:
        model = Bus
        fields = [
            "bus_id",
            "bus_number",
            "license_plate",
            "route",
            "route_name",
            "capacity",
            "device_id",
            "status",
            "manufacturer",
            "model",
            "year",
            "last_maintenance",
            "assigned_students_count",
            "utilization_percentage",
            "is_available",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["bus_id", "created_at", "updated_at"]

    def validate_capacity(self, value):
        """Validate capacity is positive"""
        if value <= 0:
            raise serializers.ValidationError("Capacity must be greater than 0")
        return value

    def validate_year(self, value):
        """Validate manufacturing year is reasonable"""
        from datetime import datetime

        current_year = datetime.now().year
        if value and (value < 2000 or value > current_year + 1):
            raise serializers.ValidationError(f"Year must be between 2000 and {current_year + 1}")
        return value


class BusAssignmentSerializer(serializers.Serializer):
    """Serializer for bulk bus-student assignments"""

    bus_id = serializers.UUIDField()
    student_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)

    def validate_bus_id(self, value):
        """Validate bus exists and is active"""
        if not Bus.objects.filter(bus_id=value, status="active").exists():
            raise serializers.ValidationError("Bus not found or not active")
        return value

    def validate_student_ids(self, value):
        """Validate all students exist"""
        from students.models import Student

        existing_ids = set(Student.objects.filter(student_id__in=value).values_list("student_id", flat=True))

        missing_ids = set(value) - existing_ids
        if missing_ids:
            raise serializers.ValidationError(f"Students not found: {list(missing_ids)}")

        return value
