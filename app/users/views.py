from django.contrib.auth.models import Group
from drf_spectacular.utils import OpenApiExample, extend_schema, inline_serializer
from rest_framework import serializers, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import APIKey, AuditLog, User
from .serializers import (
    APIKeyCreateSerializer,
    APIKeySerializer,
    AuditLogSerializer,
    GroupSerializer,
    UserSerializer,
)

# pylint: disable=no-member


class GroupViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Groups (Roles).
    Read-only following IAM principle - groups managed via seed_groups command.
    Groups represent user roles: school_admin, parent, driver.
    """

    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated]


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        return UserSerializer

    def get_queryset(self):
        queryset = User.objects.all()
        # School admins can only see users in their school (future enhancement)
        # Parents can only see themselves (future enhancement)
        return queryset

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def me(self, request):
        """Get current authenticated user information"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


class APIKeyViewSet(viewsets.ModelViewSet):
    queryset = APIKey.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return APIKeyCreateSerializer
        return APIKeySerializer

    def get_queryset(self):
        return APIKey.objects.filter(is_active=True)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        api_key = self.get_object()
        api_key.is_active = False
        api_key.save()

        # Log the revocation
        AuditLog.objects.create(
            user=request.user,
            action="UPDATE",
            resource_type="api_key",
            resource_id=str(api_key.key_id),
            changes={"is_active": False},
            ip_address=self.get_client_ip(request),
        )

        return Response({"status": "API key revoked"})

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("user").order_by("-timestamp")
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by date range
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")

        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)

        # Filter by user
        user_id = self.request.query_params.get("user_id")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        # Filter by action
        action = self.request.query_params.get("action")
        if action:
            queryset = queryset.filter(action=action)

        # Filter by resource type
        resource_type = self.request.query_params.get("resource_type")
        if resource_type:
            queryset = queryset.filter(resource_type=resource_type)

        return queryset


@extend_schema(
    responses={
        200: inline_serializer(
            name="ParentBusLocationsResponse",
            fields={
                "type": serializers.CharField(default="FeatureCollection"),
                "features": serializers.ListField(child=serializers.DictField(), help_text="GeoJSON features array"),
            },
        ),
        403: {"description": "Access denied - not a parent or not authenticated"},
    },
    operation_id="parent_bus_locations",
    description="""
    **Fortune 500 IAM-style Parent Bus Locations**

    Returns bus locations ONLY for buses assigned to the parent's children.

    **Authorization:**
    - Requires authentication (JWT token)
    - Requires role: parent
    - Filters results by parent-child-bus assignments
    - Zero-trust: Parents can ONLY see their own children's buses

    **Response:**
    GeoJSON FeatureCollection with bus location points
    """,
    tags=["Parents"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def parent_bus_locations(request):
    """
    Parent-specific bus locations endpoint (IAM-filtered).

    Returns ONLY buses assigned to the authenticated parent's children.
    """
    from django.db.models import Max
    from django.http import JsonResponse

    from kiosks.models import BusLocation

    # IAM Check: User must be a parent
    if not (hasattr(request.user, "is_parent") and request.user.is_parent):
        return JsonResponse(
            {
                "error": "Access denied - insufficient permissions",
                "required_role": "parent",
                "your_groups": list(request.user.groups.values_list("name", flat=True)),
            },
            status=403,
        )

    # Get parent's children's bus assignments
    # TODO: Query students table to find buses assigned to this parent's children
    # For now, return empty (implement when Student-Parent relationship is defined)
    from students.models import Student

    # Get children of this parent
    children = Student.objects.filter(parent=request.user)

    # Get bus IDs assigned to these children
    bus_ids = children.values_list("assigned_bus_id", flat=True).distinct()

    # Get latest locations for these specific buses only
    latest_locations = BusLocation.objects.filter(kiosk__bus_id__in=bus_ids).values("kiosk_id").annotate(latest_timestamp=Max("timestamp"))

    bus_locations = []
    for loc_data in latest_locations:
        location = (
            BusLocation.objects.filter(kiosk_id=loc_data["kiosk_id"], timestamp=loc_data["latest_timestamp"]).select_related("kiosk__bus").first()
        )

        if location:
            kiosk = location.kiosk
            if kiosk.bus:
                bus_name = kiosk.bus.license_plate
                bus_status = kiosk.bus.get_status_display()
            else:
                bus_name = f"Kiosk {kiosk.kiosk_id}"
                bus_status = "Unassigned"

            bus_locations.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [location.longitude, location.latitude]},
                    "properties": {
                        "id": kiosk.kiosk_id,
                        "name": bus_name,
                        "status": bus_status,
                        "last_update": location.timestamp.isoformat(),
                        "speed": location.speed,
                        "heading": location.heading,
                    },
                }
            )

    return JsonResponse({"type": "FeatureCollection", "features": bus_locations})
