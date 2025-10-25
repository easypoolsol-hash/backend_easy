from django.contrib.auth import authenticate
from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import APIKey, AuditLog, Role, User
from .serializers import (
    APIKeyCreateSerializer,
    APIKeySerializer,
    AuditLogSerializer,
    RoleSerializer,
    UserCreateSerializer,
    UserSerializer,
)
from .token_config import create_user_token

# pylint: disable=no-member


class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Role.objects.filter(is_active=True)
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def get_queryset(self):
        queryset = User.objects.select_related("role")
        # School admins can only see users in their school (future enhancement)
        # Parents can only see themselves (future enhancement)
        return queryset

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def me(self, request):
        """Get current authenticated user information"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], permission_classes=[])
    def login(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"error": "Username and password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(username=username, password=password)
        if user:
            # CRITICAL SEPARATION: This endpoint is ONLY for HUMAN USERS
            # Endpoint: POST /api/v1/users/login/
            # Auth Method: Username + Password
            # Token Config: users/token_config.py (1 day refresh token)
            #
            # Kiosks are COMPLETELY SEPARATE:
            # Endpoint: POST /api/v1/kiosk/activate/
            # Auth Method: Activation Token (one-time use)
            # Token Config: kiosks/token_config.py (60 day refresh token)
            #
            # SOLID Principle: Single file responsible for each token type
            # DRY Principle: No code duplication, explicit configuration
            # KISS Principle: Simple, clear separation
            refresh = create_user_token(user)

            user.last_login = timezone.now()
            user.save(update_fields=["last_login"])

            # Log the login
            AuditLog.objects.create(
                user=user,
                action="LOGIN",
                resource_type="user",
                resource_id=str(user.user_id),
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )

            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "user": UserSerializer(user).data,
                }
            )

        return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated])
    def logout(self, request):
        """
        Logout endpoint - Blacklists refresh token (Fortune 500 standard)

        Security: Prevents token reuse even if stolen

        Request Body: { "refresh": "..." }
        Returns: 200 { "message": "Logout successful" }
        """
        try:
            refresh_token = request.data.get("refresh")

            if not refresh_token:
                return Response({"error": "Refresh token required"}, status=status.HTTP_400_BAD_REQUEST)

            # Blacklist the refresh token (prevents reuse)
            token = RefreshToken(refresh_token)
            token.blacklist()

            # Log the logout
            AuditLog.objects.create(
                user=request.user,
                action="LOGOUT",
                resource_type="user",
                resource_id=str(request.user.user_id),
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )

            return Response({"message": "Logout successful"}, status=status.HTTP_200_OK)

        except TokenError as e:
            return Response({"error": f"Invalid or expired token: {e!s}"}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({"error": f"Logout failed: {e!s}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
    description="""
    Custom TokenRefreshView that supports both regular JWT and kiosk JWT tokens.

    **Token Rotation Security:**
    - Accepts: refresh token only
    - Returns: NEW access token (15 min) + NEW refresh token (60 days)
    - Old refresh token is immediately blacklisted (cannot be reused)
    """,
    request=inline_serializer(
        name="TokenRefreshRequest",
        fields={
            "refresh": serializers.CharField(help_text="The refresh token obtained from activation or previous refresh"),
        },
    ),
    responses={
        200: inline_serializer(
            name="TokenRefreshResponse",
            fields={
                "access": serializers.CharField(help_text="New access token (valid for 15 minutes)"),
                "refresh": serializers.CharField(help_text="New refresh token (valid for 60 days). Old refresh token is now blacklisted."),
            },
        ),
    },
    examples=[
        OpenApiExample(
            "Successful Token Refresh",
            description="Example of successful token refresh with rotation",
            value={"refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."},
            request_only=True,
        ),
    ],
)
class KioskTokenRefreshView(TokenRefreshView):
    """
    Custom TokenRefreshView that supports both regular JWT and kiosk JWT tokens.

    This ensures kiosk devices can refresh their tokens without authentication failures.
    """

    pass


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
                "your_role": request.user.role.name if hasattr(request.user, "role") else None,
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
