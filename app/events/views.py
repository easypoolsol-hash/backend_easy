from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from bus_kiosk_backend.permissions import IsSchoolAdmin
from kiosks.authentication import KioskJWTAuthentication
from kiosks.permissions import IsKiosk
from students.models import Student

from .models import AttendanceRecord, BoardingEvent
from .serializers import (
    AttendanceRecordSerializer,
    AttendanceSummarySerializer,
    BoardingEventCreateSerializer,
    BoardingEventSerializer,
)


class BoardingEventViewSet(viewsets.ModelViewSet):
    """
    ViewSet for boarding events

    PERMISSIONS:
    - CREATE/BULK: IsKiosk (kiosk devices only)
    - LIST/RETRIEVE/UPDATE/DELETE: IsSchoolAdmin (school admins only)
    - RECENT: IsSchoolAdmin (school admins only)

    NOTE: Old permission was IsAuthenticated (too permissive!)
    Now using AWS-style deny-by-default with explicit permissions.
    """

    queryset = BoardingEvent.objects.select_related("student").order_by(
        "-timestamp"
    )
    authentication_classes = [KioskJWTAuthentication]
    permission_classes = [
        IsSchoolAdmin
    ]  # Default: school admin only for list/retrieve
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["kiosk_id", "student", "timestamp", "bus_route"]

    def get_serializer_class(self):
        if self.action == "create":
            return BoardingEventCreateSerializer
        return BoardingEventSerializer

    def get_permissions(self):
        """
        AWS-style explicit permissions:
        - Kiosks can CREATE boarding events
        - School admins can LIST/RETRIEVE/UPDATE/DELETE
        """
        if self.action in ["create", "bulk_create"]:
            return [IsKiosk()]
        # All other actions (list, retrieve, update, delete, recent)
        return [IsSchoolAdmin()]

    def get_queryset(self):
        """Filter queryset based on user role"""
        queryset = super().get_queryset()

        if hasattr(self.request.user, "role"):
            if self.request.user.role == "parent":
                # Parents can only see their children's events
                student_ids = Student.objects.filter(student_parents__parent__user=self.request.user).values_list("student_id", flat=True)
                queryset = queryset.filter(student_id__in=student_ids)
            elif self.request.user.role == "school_admin":
                # School admins can see all events in their school
                # This would need school filtering logic
                pass

        return queryset

    @action(detail=False, methods=["post"], url_path="bulk")
    def bulk_create(self, request):
        """Bulk create boarding events (for high-throughput kiosk operations)"""
        serializer = BoardingEventCreateSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        events = serializer.save()
        return Response(
            {"created": len(events), "events": [e.event_id for e in events]},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="recent")
    def recent_events(self, request):
        """Get recent boarding events for dashboard"""
        hours = int(request.query_params.get("hours", 24))
        since = timezone.now() - timedelta(hours=hours)

        events = self.get_queryset().filter(timestamp__gte=since)[:100]
        serializer = self.get_serializer(events, many=True)
        return Response(serializer.data)


class AttendanceRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for attendance records

    PERMISSION: IsSchoolAdmin (school administrators only)

    NOTE: Old permission was IsAuthenticated (too permissive!)
    Now using AWS-style deny-by-default with explicit permissions.
    """

    queryset = AttendanceRecord.objects.select_related("student").order_by(
        "-date"
    )
    serializer_class = AttendanceRecordSerializer
    permission_classes = [
        IsSchoolAdmin
    ]  # School admins only (no kiosks, no parents)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["student", "date", "status"]

    def get_queryset(self):
        """Filter queryset based on user role"""
        queryset = super().get_queryset()

        if hasattr(self.request.user, "role"):
            if self.request.user.role == "parent":
                # Parents can only see their children's attendance
                student_ids = Student.objects.filter(student_parents__parent__user=self.request.user).values_list("student_id", flat=True)
                queryset = queryset.filter(student_id__in=student_ids)
            elif self.request.user.role == "school_admin":
                # School admins can see all attendance in their school
                pass

        return queryset

    @action(detail=False, methods=["get"], url_path="summary")
    def attendance_summary(self, request):
        """Get attendance summary for date range"""
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        if not start_date or not end_date:
            return Response(
                {"error": "start_date and end_date parameters required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Aggregate attendance data
        summary_data = AttendanceRecord.objects.filter(date__range=[start_date, end_date]).aggregate(
            total_students=Count("student", distinct=True),
            present_count=Count("record_id", filter=Q(status="present")),
            absent_count=Count("record_id", filter=Q(status="absent")),
            partial_count=Count("record_id", filter=Q(status="partial")),
        )

        if summary_data["total_students"] > 0:
            summary_data["attendance_rate"] = summary_data["present_count"] / summary_data["total_students"]
        else:
            summary_data["attendance_rate"] = 0

        summary_data["date"] = f"{start_date} to {end_date}"

        serializer = AttendanceSummarySerializer(summary_data)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="student/(?P<student_id>[^/.]+)")
    def student_attendance(self, request, student_id=None):
        """Get attendance history for a specific student"""
        try:
            student = Student.objects.get(student_id=student_id)
        except Student.DoesNotExist:
            return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

        # Check permissions
        if hasattr(request.user, "role") and request.user.role == "parent" and not student.student_parents.filter(parent__user=request.user).exists():
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        records = self.get_queryset().filter(student=student)
        serializer = self.get_serializer(records, many=True)
        return Response(serializer.data)
