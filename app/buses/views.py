from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from bus_kiosk_backend.permissions import IsSchoolAdmin
from students.models import Student

from .models import Bus, Route
from .serializers import BusAssignmentSerializer, BusSerializer, RouteSerializer
from .services import LocationService


class RouteViewSet(viewsets.ModelViewSet):
    """ViewSet for bus routes"""

    queryset = Route.objects.prefetch_related("buses", "route_stops__bus_stop", "route_waypoints__waypoint").order_by("name")
    serializer_class = RouteSerializer
    permission_classes = [IsSchoolAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["is_active"]

    # Removed get_permissions() - all actions require IsSchoolAdmin

    @action(detail=True, methods=["get"], url_path="buses")
    def route_buses(self, request, pk=None):
        """Get all buses assigned to this route"""
        route = self.get_object()
        buses = route.buses.all()
        serializer = BusSerializer(buses, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="students")
    def route_students(self, request, pk=None):
        """Get all students assigned to buses on this route"""
        route = self.get_object()
        students = Student.objects.filter(assigned_bus__route=route, status="active").select_related("assigned_bus")
        # Return basic student info (would need StudentSerializer)
        data = [
            {
                "student_id": str(s.student_id),
                "name": s.name,
                "grade": s.grade,
                "bus_license_plate": (
                    s.assigned_bus.license_plate if s.assigned_bus else None  # type: ignore[attr-defined]
                ),
            }
            for s in students
        ]
        return Response(data)


class BusViewSet(viewsets.ModelViewSet):
    """ViewSet for buses"""

    queryset = Bus.objects.select_related("route").prefetch_related("assigned_students").order_by("license_plate")
    serializer_class = BusSerializer
    permission_classes = [IsSchoolAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["route", "status", "device_id"]

    # Removed get_permissions() - all actions require IsSchoolAdmin

    @action(detail=True, methods=["get"], url_path="students")
    def bus_students(self, request, pk=None):
        """Get all students assigned to this bus"""
        bus = self.get_object()
        students = bus.assigned_students.filter(status="active")
        # Return basic student info (would need StudentSerializer)
        data = [
            {
                "student_id": str(s.student_id),
                "name": s.name,
                "grade": s.grade,
                "section": s.section,
            }
            for s in students
        ]
        return Response(data)

    @action(detail=False, methods=["post"], url_path="assign-students")
    def assign_students(self, request):
        """Bulk assign students to buses"""
        serializer = BusAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        bus_id = serializer.validated_data["bus_id"]
        student_ids = serializer.validated_data["student_ids"]

        with transaction.atomic():
            # Get the bus
            bus = get_object_or_404(Bus, bus_id=bus_id)

            # Check capacity
            current_count = bus.assigned_students.filter(status="active").count()
            if current_count + len(student_ids) > bus.capacity:
                return Response(
                    {"error": f"Bus capacity exceeded. Current: {current_count}, Adding: {len(student_ids)}, Capacity: {bus.capacity}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Update student assignments
            Student.objects.filter(student_id__in=student_ids).update(assigned_bus=bus)

        return Response(
            {
                "message": f"Successfully assigned {len(student_ids)} students to bus {bus.license_plate}",
                "bus_id": str(bus_id),
                "assigned_count": len(student_ids),
            }
        )

    @action(detail=False, methods=["get"], url_path="utilization")
    def utilization_report(self, request):
        """Get fleet utilization report"""
        buses = Bus.objects.filter(status="active").select_related("route")

        data = []
        for bus in buses:
            data.append(
                {
                    "bus_id": str(bus.bus_id),
                    "license_plate": bus.license_plate,
                    "route": bus.route.name if bus.route else None,
                    "capacity": bus.capacity,
                    "assigned_students": bus.assigned_students_count,
                    "utilization_percentage": round(bus.utilization_percentage, 1),
                    "available_seats": bus.capacity - bus.assigned_students_count,
                }
            )

        # Summary stats
        total_capacity = sum(b["capacity"] for b in data)
        total_assigned = sum(b["assigned_students"] for b in data)
        overall_utilization = (total_assigned / total_capacity * 100) if total_capacity > 0 else 0

        return Response(
            {
                "buses": data,
                "summary": {
                    "total_buses": len(data),
                    "total_capacity": total_capacity,
                    "total_assigned": total_assigned,
                    "overall_utilization": round(overall_utilization, 1),
                },
            }
        )


@extend_schema(
    responses={
        200: inline_serializer(
            name="BusLocationsResponse",
            fields={
                "type": serializers.CharField(default="FeatureCollection"),
                "features": serializers.ListField(
                    child=serializers.DictField(),
                    help_text="Array of GeoJSON Feature objects with bus locations",
                ),
            },
        ),
    },
    operation_id="bus_locations_api",
    description="""
    Returns real-time bus locations for ALL buses in the fleet as GeoJSON.

    Accessible by any authenticated user (school administrators, staff, etc.).

    **Response Format:**
    GeoJSON FeatureCollection with Point geometries for each bus location.

    Each feature includes properties:
    - id: Kiosk ID
    - name: Bus license plate
    - status: Bus status
    - last_update: Timestamp of last location update
    - speed: Current speed (km/h)
    - heading: Direction heading (degrees)
    """,
    tags=["Buses"],
)
@api_view(["GET"])
@permission_classes([IsSchoolAdmin])
@cache_page(30)  # Cache for 30 seconds to protect database from polling load
def bus_locations_api(request):
    """
    Bus locations API for school dashboard (school administrators only).

    Returns real-time bus locations for ALL buses in the fleet as GeoJSON.
    Accessible by any authenticated user.

    Cached for 30 seconds to protect database (100 buses x polling = high load).
    """
    # Get latest GPS location for each bus
    from kiosks.models import BusLocation

    latest_locations = BusLocation.objects.values("kiosk_id").annotate(latest_timestamp=Max("timestamp"))

    bus_locations = []
    for loc_data in latest_locations:
        location = (
            BusLocation.objects.filter(kiosk_id=loc_data["kiosk_id"], timestamp=loc_data["latest_timestamp"]).select_related("kiosk__bus").first()
        )

        if location and location.kiosk and location.kiosk.bus:
            kiosk = location.kiosk
            bus = kiosk.bus

            bus_locations.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [location.longitude, location.latitude]},
                    "properties": {
                        "id": kiosk.kiosk_id,  # Frontend expects "id"
                        "name": bus.license_plate,  # Frontend expects "name"
                        "status": bus.get_status_display(),
                        "kiosk_id": kiosk.kiosk_id,
                        "bus_name": bus.license_plate,
                        "bus_number": bus.bus_number,  # School-assigned bus number (e.g., BUS-001)
                        "last_update": location.timestamp.isoformat(),
                        "speed": location.speed,
                        "heading": location.heading,
                    },
                }
            )

    return JsonResponse({"type": "FeatureCollection", "features": bus_locations})


@extend_schema(
    responses={
        200: inline_serializer(
            name="BusLocationHistoryResponse",
            fields={
                "type": serializers.CharField(default="FeatureCollection"),
                "features": serializers.ListField(
                    child=serializers.DictField(),
                    help_text="Array of GeoJSON Feature objects with historical bus locations",
                ),
            },
        ),
    },
    operation_id="bus_locations_history_api",
    parameters=[
        OpenApiParameter(
            name="bus_uuid",
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.QUERY,
            required=True,
            description="Bus UUID (primary key)",
        ),
        OpenApiParameter(
            name="date",
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            required=True,
            description="Date in YYYY-MM-DD format (max 7 days in the past)",
        ),
    ],
    description="""
    Returns historical bus locations for a specific bus on a specific date as GeoJSON.

    Accessible by school administrators only.

    **Response Format:**
    GeoJSON FeatureCollection with Point geometries for each location record.

    Each feature includes properties:
    - id: Location record ID
    - bus_number: Bus identifier
    - bus_name: Bus license plate
    - timestamp: When the location was recorded
    - speed: Speed at that moment (km/h)
    - heading: Direction heading (degrees)
    - accuracy: GPS accuracy (meters)
    """,
    tags=["Buses"],
)
@api_view(["GET"])
@permission_classes([IsSchoolAdmin])
def bus_locations_history_api(request):
    """
    Historical bus locations API for playback feature (school administrators only).

    Returns all location records for a specific bus on a specific date.
    No caching - historical data doesn't change.
    """
    from kiosks.models import BusLocation

    # Get query parameters
    bus_uuid = request.GET.get("bus_uuid")
    date_str = request.GET.get("date")

    # Validate required parameters
    if not bus_uuid:
        return Response({"error": "bus_uuid parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

    if not date_str:
        return Response({"error": "date parameter is required (YYYY-MM-DD format)"}, status=status.HTTP_400_BAD_REQUEST)

    # Parse and validate date
    try:
        requested_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return Response({"error": "Invalid date format. Use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)

    # Validate date range (max 7 days in the past)
    today = timezone.now().date()
    max_past_date = today - timedelta(days=7)

    if requested_date > today:
        return Response({"error": "Cannot request future dates"}, status=status.HTTP_400_BAD_REQUEST)

    if requested_date < max_past_date:
        return Response({"error": "Can only retrieve history up to 7 days in the past"}, status=status.HTTP_400_BAD_REQUEST)

    # Get start and end of the requested day (timezone-aware)
    start_time = timezone.make_aware(datetime.combine(requested_date, datetime.min.time()))
    end_time = timezone.make_aware(datetime.combine(requested_date, datetime.max.time()))

    # Query historical locations
    locations = (
        BusLocation.objects.filter(kiosk__bus__bus_id=bus_uuid, timestamp__gte=start_time, timestamp__lte=end_time)
        .select_related("kiosk__bus")
        .order_by("timestamp")
    )

    if not locations.exists():
        return JsonResponse({"type": "FeatureCollection", "features": []})

    # Build GeoJSON features
    features = []
    for location in locations:
        kiosk = location.kiosk
        bus = kiosk.bus if kiosk else None

        if bus:
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [location.longitude, location.latitude]},
                    "properties": {
                        "id": location.location_id,
                        "bus_number": bus.bus_number,
                        "bus_name": bus.license_plate,
                        "kiosk_id": kiosk.kiosk_id,
                        "timestamp": location.timestamp.isoformat(),
                        "speed": location.speed,
                        "heading": location.heading,
                        "accuracy": location.accuracy,
                    },
                }
            )

    return JsonResponse({"type": "FeatureCollection", "features": features})


# ============================================================================
# DEPRECATED: Wrong Parent Bus Location API
# ============================================================================
# This API was incorrectly implemented and is NOT used by parent_easy app.
# The correct parent APIs are:
#   - /api/v1/parents/me/bus-locations/ (students/views.py - ParentMeViewSet.bus_locations)
#   - /api/v1/users/parent/my-buses/ (users/views.py - parent_bus_locations)
#
# Commented out for potential future use if needed, but should NOT be used.
# ============================================================================
#
# @extend_schema(
#     responses={
#         200: inline_serializer(
#             name="ParentBusLocationResponse",
#             fields={
#                 "type": serializers.CharField(default="Feature"),
#                 "geometry": serializers.DictField(
#                     help_text="GeoJSON Point geometry with bus location",
#                 ),
#                 "properties": serializers.DictField(
#                     help_text="Bus details including bus_id, name, status, etc.",
#                 ),
#             },
#         ),
#     },
#     operation_id="parent_bus_location_api",
#     description="""
#     Returns real-time bus location for the parent's child's assigned bus only.
#
#     Security: Parents can ONLY see their own child's bus location, not other buses.
#
#     **Response Format:**
#     GeoJSON Feature with Point geometry for the bus location.
#
#     Returns 404 if:
#     - Parent has no students assigned
#     - Student has no bus assigned
#     - No recent location data available
#     """,
#     tags=["Buses"],
# )
# @api_view(["GET"])
# @permission_classes([IsAuthenticated])
# def parent_bus_location_api(request):
#     """
#     Parent-specific bus location API.
#
#     Returns location for ONLY the bus that the parent's child is assigned to.
#     This provides privacy and security - parents cannot see other buses.
#     """
#     from kiosks.models import BusLocation
#     from students.models import Parent
#
#     # Get authenticated user's parent record
#     # Assuming request.user has a related parent record or we use email/phone to match
#     try:
#         # Try to find parent by Firebase email
#         user_email = request.user.email if hasattr(request.user, "email") else None
#
#         if not user_email:
#             return Response({"error": "Unable to identify parent account"}, status=status.HTTP_400_BAD_REQUEST)
#
#         # Find parent by email (encrypted field)
#         parent = None
#         for p in Parent.objects.all():
#             if p.encrypted_email == user_email:
#                 parent = p
#                 break
#
#         if not parent:
#             return Response({"error": "Parent account not found"}, status=status.HTTP_404_NOT_FOUND)
#
#         # Get parent's students
#         students = parent.get_students()
#
#         if not students.exists():
#             return Response({"error": "No students assigned to this parent"}, status=status.HTTP_404_NOT_FOUND)
#
#         # Get first student's assigned bus (assuming one child per parent for now)
#         student = students.first()
#
#         if not student.assigned_bus:
#             return Response({"error": "Student has no bus assigned"}, status=status.HTTP_404_NOT_FOUND)
#
#         bus = student.assigned_bus
#
#         # Get latest location for this bus
#         kiosk = getattr(bus, "kiosk", None)
#
#         if not kiosk:
#             return Response({"error": "Bus has no active kiosk device"}, status=status.HTTP_404_NOT_FOUND)
#
#         # Get most recent location
#         latest_location = BusLocation.objects.filter(kiosk=kiosk).order_by("-timestamp").first()
#
#         if not latest_location:
#             return Response({"error": "No location data available for this bus"}, status=status.HTTP_404_NOT_FOUND)
#
#         # Return GeoJSON Feature
#         return JsonResponse(
#             {
#                 "type": "Feature",
#                 "geometry": {"type": "Point", "coordinates": [latest_location.longitude, latest_location.latitude]},
#                 "properties": {
#                     "id": kiosk.kiosk_id,
#                     "bus_id": str(bus.bus_id),
#                     "bus_number": bus.bus_number,
#                     "name": bus.license_plate,
#                     "status": bus.get_status_display(),
#                     "last_update": latest_location.timestamp.isoformat(),
#                     "speed": latest_location.speed,
#                     "heading": latest_location.heading,
#                     "accuracy": latest_location.accuracy,
#                 },
#             }
#         )
#
#     except Exception as e:
#         return Response({"error": f"Failed to retrieve bus location: {e!s}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([IsSchoolAdmin])
def geocode_address(request):
    """
    Geocode an address to coordinates.

    POST /api/v1/geocode/
    Body: {"address": "Imperial College London"}

    Returns: {
        "latitude": 51.4988,
        "longitude": -0.1749,
        "formatted_address": "Imperial College London, Exhibition Rd, London SW7 2AZ, UK"
    }
    """
    address = request.data.get("address")

    if not address:
        return Response({"error": "Address field is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        location_service = LocationService()
        result = location_service.geocode_address(address)
        return Response(result, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": f"Geocoding service error: {e!s}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
