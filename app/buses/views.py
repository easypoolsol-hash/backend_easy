from django.db import transaction
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from students.models import Student

from .models import Bus, Route
from .serializers import BusAssignmentSerializer, BusSerializer, RouteSerializer
from .services import LocationService


class RouteViewSet(viewsets.ModelViewSet):
    """ViewSet for bus routes"""

    queryset = Route.objects.prefetch_related("buses", "route_stops__bus_stop", "route_waypoints__waypoint").order_by("name")
    serializer_class = RouteSerializer
    permission_classes = [IsAuthenticated]
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
    permission_classes = [IsAuthenticated]
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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def bus_locations_api(request):
    """
    Bus locations API for school dashboard (any authenticated user).

    Returns real-time bus locations for ALL buses in the fleet as GeoJSON.
    Accessible by any authenticated user.
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
                        "last_update": location.timestamp.isoformat(),
                        "speed": location.speed,
                        "heading": location.heading,
                    },
                }
            )

    return JsonResponse({"type": "FeatureCollection", "features": bus_locations})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
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
