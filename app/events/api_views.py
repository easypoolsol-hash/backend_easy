"""REST API views for school dashboard (Flutter app)."""

from django.core.cache import cache
from django.db.models import Count, Prefetch, Q
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from buses.models import Bus
from students.models import Student

from .dashboard_serializers import (
    DashboardStatsSerializer,
    DashboardStudentsResponseSerializer,
)
from .models import BoardingEvent


class DashboardStatsAPIView(APIView):
    """
    Dashboard statistics API - Returns summary stats for school
    dashboard.
    Cached for 10 seconds in Redis for performance.

    PERMISSION: IsAuthenticated (any authenticated user)
    """

    permission_classes = [IsAuthenticated]
    serializer_class = DashboardStatsSerializer

    @extend_schema(
        summary="Get dashboard summary statistics",
        description=("Returns summary statistics for school dashboard (buses, students boarded) for TODAY only. Cached for 10 seconds."),
        responses={200: DashboardStatsSerializer},
    )
    def get(self, request):
        """Get dashboard stats for today only."""
        # Always use today (no date parameter)
        target_date = timezone.now().date()

        # Try to get from cache
        cache_key = f"dashboard_stats_{target_date}"
        cached_stats = cache.get(cache_key)
        if cached_stats:
            return Response(cached_stats)

        # Calculate stats
        total_buses = Bus.objects.count()
        active_buses = Bus.objects.filter(status="active").count()

        # Students who boarded on this date (distinct count)
        students_boarded = BoardingEvent.objects.filter(timestamp__date=target_date).values("student").distinct().count()

        # Total events on this date
        total_events = BoardingEvent.objects.filter(timestamp__date=target_date).count()

        stats = {
            "date": str(target_date),
            "active_buses": active_buses,
            "total_buses": total_buses,
            "students_boarded_today": students_boarded,
            "total_events_today": total_events,
            "last_updated": timezone.now().isoformat(),
        }

        # Cache for 10 seconds
        cache.set(cache_key, stats, timeout=10)

        return Response(stats)


class DashboardStudentsAPIView(APIView):
    """
    Dashboard students activity API - Returns list of students who
    boarded on a specific date with all their boarding events.

    PERMISSION: IsAuthenticated (any authenticated user)
    """

    permission_classes = [IsAuthenticated]
    serializer_class = DashboardStudentsResponseSerializer

    @extend_schema(
        summary="Get students with boarding events",
        description=("Returns paginated list of students who boarded TODAY with all their events"),
        parameters=[
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Number of students per page (default=50)",
            ),
            OpenApiParameter(
                name="offset",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Offset for pagination (default=0)",
            ),
        ],
        responses={200: DashboardStudentsResponseSerializer},
    )
    def get(self, request):
        """Get students with boarding events for today only."""
        # Always use today (no date parameter)
        target_date = timezone.now().date()

        # Pagination params
        try:
            limit = int(request.query_params.get("limit", 50))
            offset = int(request.query_params.get("offset", 0))
        except ValueError:
            return Response(
                {"error": "Invalid limit or offset"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get students who have boarding events on this date
        students_query = (
            Student.objects.filter(boarding_events__timestamp__date=target_date)
            .select_related("assigned_bus__route")
            .prefetch_related(
                Prefetch(
                    "boarding_events",
                    queryset=BoardingEvent.objects.filter(timestamp__date=target_date).order_by("timestamp"),
                    to_attr="todays_events",
                )
            )
            .annotate(
                event_count=Count(
                    "boarding_events",
                    filter=Q(boarding_events__timestamp__date=target_date),
                )
            )
            .distinct()
        )

        # Get total count
        total_count = students_query.count()

        # Apply pagination
        students = students_query[offset : offset + limit]

        # Build response
        results = []
        for student in students:
            # Get bus and route info
            bus_number = None
            route_name = None
            if student.assigned_bus:
                bus_number = student.assigned_bus.license_plate
                if student.assigned_bus.route:
                    route_name = student.assigned_bus.route.name

            # Build events list
            events = [
                {
                    "event_id": event.event_id,
                    "timestamp": event.timestamp,
                    "kiosk_id": event.kiosk_id,
                    "event_type": event.metadata.get("event_type", "boarding"),
                }
                for event in student.todays_events
            ]

            results.append(
                {
                    "school_student_id": student.school_student_id,
                    "student_name": student.encrypted_name,
                    "grade": student.grade,
                    "bus_number": bus_number,
                    "route_name": route_name,
                    "events": events,
                    "event_count": len(events),
                }
            )

        return Response(
            {
                "count": total_count,
                "next": offset + limit < total_count,
                "previous": offset > 0,
                "results": results,
            }
        )
