from rest_framework import serializers

from .models import Bus, BusStop, Route, RouteStop


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
    latitude = serializers.DecimalField(source="bus_stop.latitude", max_digits=10, decimal_places=7, read_only=True)
    longitude = serializers.DecimalField(source="bus_stop.longitude", max_digits=10, decimal_places=7, read_only=True)

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


class RouteSerializer(serializers.ModelSerializer):
    """Serializer for bus routes"""

    stop_count = serializers.ReadOnlyField()
    total_students = serializers.ReadOnlyField()
    route_stops = RouteStopSerializer(many=True, read_only=True)

    class Meta:
        model = Route
        fields = [
            "route_id",
            "name",
            "description",
            "is_active",
            "stop_count",
            "total_students",
            "route_stops",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["route_id", "created_at", "updated_at"]


class BusSerializer(serializers.ModelSerializer):
    """Serializer for buses"""

    route_name = serializers.CharField(source="route.name", read_only=True)
    assigned_students_count = serializers.ReadOnlyField()
    utilization_percentage = serializers.ReadOnlyField()
    is_available = serializers.ReadOnlyField()

    class Meta:
        model = Bus
        fields = [
            "bus_id",
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
