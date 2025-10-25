"""Serializers for school dashboard API endpoints."""

from rest_framework import serializers


class DashboardStatsSerializer(serializers.Serializer):
    """Serializer for dashboard statistics response."""

    date = serializers.DateField(help_text="Date for stats (YYYY-MM-DD)")
    active_buses = serializers.IntegerField(help_text="Number of active buses")
    total_buses = serializers.IntegerField(help_text="Total buses in fleet")
    students_boarded_today = serializers.IntegerField(help_text="Unique students who boarded today")
    total_events_today = serializers.IntegerField(help_text="Total boarding events today")
    last_updated = serializers.DateTimeField(help_text="When this data was last calculated")


class BoardingEventNestedSerializer(serializers.Serializer):
    """Nested boarding event for student activity."""

    event_id = serializers.CharField(help_text="Event ULID")
    timestamp = serializers.DateTimeField(help_text="When event occurred")
    kiosk_id = serializers.CharField(help_text="Kiosk device ID")
    event_type = serializers.CharField(help_text="Event type (boarding/pickup/dropoff)")


class StudentActivitySerializer(serializers.Serializer):
    """Serializer for student activity with boarding events.

    SECURITY: Does NOT expose internal student_id UUID to dashboard
    Uses school_student_id (human-readable) instead
    """

    school_student_id = serializers.CharField(help_text="School-provided student ID (e.g., STU-2024-001)")
    student_name = serializers.CharField(help_text="Student name (decrypted by backend)")
    grade = serializers.CharField(help_text="Student grade")
    bus_number = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Bus license plate",
    )
    route_name = serializers.CharField(required=False, allow_null=True, help_text="Route name")
    events = BoardingEventNestedSerializer(many=True, help_text="All boarding events for this student today")
    event_count = serializers.IntegerField(help_text="Number of events today")


class DashboardStudentsResponseSerializer(serializers.Serializer):
    """Paginated response for dashboard students."""

    count = serializers.IntegerField(help_text="Total number of students with events")
    next = serializers.BooleanField(help_text="Has next page")
    previous = serializers.BooleanField(help_text="Has previous page")
    results = StudentActivitySerializer(many=True, help_text="List of students")
