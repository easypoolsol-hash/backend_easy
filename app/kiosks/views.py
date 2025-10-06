import hashlib
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from bus_kiosk_backend.authentication import KioskJWTAuthentication
from bus_kiosk_backend.permissions import IsKiosk, IsSchoolAdmin

from .models import DeviceLog, Kiosk
from .serializers import (
    DeviceLogSerializer,
    KioskAuthResponseSerializer,
    KioskAuthSerializer,
    KioskHeartbeatSerializer,
    KioskSerializer,
    KioskStatusSerializer,
)


@extend_schema(
    request=KioskAuthSerializer,
    responses={
        200: KioskAuthResponseSerializer,
        400: OpenApiResponse(description='Invalid request'),
    },
    description='Authenticate kiosk device and receive JWT tokens'
)
@api_view(['POST'])
@permission_classes([AllowAny])
def kiosk_auth(request):
    """
    Kiosk authentication endpoint (Fortune 500 implementation)

    Authenticates kiosk devices and returns JWT tokens for API access.

    **Request:**
    ```json
    POST /api/kiosks/auth/
    {
        "kiosk_id": "TEST-KIOSK-001",
        "api_key": "test-api-key-12345"
    }
    ```

    **Success Response (200):**
    ```json
    {
        "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "kiosk_id": "TEST-KIOSK-001",
        "bus_id": "uuid-of-bus",
        "expires_in": 86400
    }
    ```

    **Error Responses:**
    - 400: Invalid request format
    - 401: Invalid credentials or inactive kiosk

    **Security Features:**
    - API key hashed using SHA-256
    - Generic error messages (no info leakage)
    - JWT tokens with configurable expiry
    - Validates kiosk active status
    """
    serializer = KioskAuthSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get authenticated kiosk from serializer context
    kiosk = serializer.context['kiosk']

    # Generate JWT tokens (Fortune 500 pattern: separate access + refresh)
    refresh = RefreshToken()
    refresh['kiosk_id'] = kiosk.kiosk_id
    refresh['type'] = 'kiosk'  # Token type for permission checking

    # Log successful authentication
    DeviceLog.log(
        kiosk=kiosk,
        level='INFO',
        message='Kiosk authenticated successfully',
        metadata={
            'ip_address': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT'),
        }
    )

    # Update last heartbeat
    kiosk.last_heartbeat = timezone.now()
    kiosk.save(update_fields=['last_heartbeat'])

    # Build response
    response_data = {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'kiosk_id': kiosk.kiosk_id,
        'bus_id': kiosk.bus.bus_id if kiosk.bus else None,
        'expires_in': 86400  # 24 hours in seconds
    }

    # Validate response structure
    response_serializer = KioskAuthResponseSerializer(data=response_data)
    response_serializer.is_valid(raise_exception=True)

    return Response(
        response_serializer.data,
        status=status.HTTP_200_OK
    )


class KioskViewSet(viewsets.ModelViewSet):
    """ViewSet for kiosk management"""

    queryset = Kiosk.objects.select_related("bus").order_by("kiosk_id")
    serializer_class = KioskSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["is_active", "bus"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsSchoolAdmin()]
        return [IsAuthenticated()]

    @action(detail=True, methods=["get"], url_path="logs")
    def kiosk_logs(self, request, pk=None):
        """Get logs for a specific kiosk"""
        kiosk = self.get_object()
        logs = kiosk.logs.order_by("-timestamp")[:100]  # Last 100 logs
        serializer = DeviceLogSerializer(logs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="status")
    def status_summary(self, request):
        """Get overall kiosk status summary"""
        kiosks = self.get_queryset()

        # Calculate status counts
        total = kiosks.count()
        active = kiosks.filter(is_active=True).count()

        # Online = active kiosks with recent heartbeat (last 5 minutes)
        five_minutes_ago = timezone.now() - timedelta(minutes=5)
        online = kiosks.filter(
            is_active=True, last_heartbeat__gte=five_minutes_ago
        ).count()

        offline = active - online

        # Serialize all kiosks
        serializer = KioskSerializer(kiosks, many=True, context={"request": request})

        summary_data = {
            "total_kiosks": total,
            "active_kiosks": active,
            "online_kiosks": online,
            "offline_kiosks": offline,
            "kiosks": serializer.data,
        }

        summary_serializer = KioskStatusSerializer(summary_data)
        return Response(summary_serializer.data)


@api_view(["POST"])
@authentication_classes([KioskJWTAuthentication])
@permission_classes([IsAuthenticated])
def kiosk_heartbeat(request):
    """
    Kiosk heartbeat endpoint - called by devices to report status.
    High-throughput endpoint for monitoring device health.

    Fortune 500 pattern:
    - Authentication: KioskJWTAuthentication (validates JWT contains kiosk)
    - Permission: IsAuthenticated (standard DRF permission)
    - request.user contains authenticated Kiosk object
    """
    # Get authenticated kiosk from request.user (set by KioskJWTAuthentication)
    kiosk = request.user

    # Security check: Ensure request.user is actually a Kiosk (not a User)
    if not isinstance(kiosk, Kiosk):
        return Response(
            {'detail': 'Authentication credentials are not valid for kiosk endpoints'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Pass kiosk to serializer for optional security check
    serializer = KioskHeartbeatSerializer(data=request.data, context={'kiosk': kiosk})
    serializer.is_valid(raise_exception=True)

    # Update kiosk with heartbeat data
    update_data = {"last_heartbeat": timezone.now()}

    if "firmware_version" in serializer.validated_data:
        update_data["firmware_version"] = serializer.validated_data["firmware_version"]
    if "battery_level" in serializer.validated_data:
        update_data["battery_level"] = serializer.validated_data["battery_level"]
    if "storage_used_mb" in serializer.validated_data:
        update_data["storage_used_mb"] = serializer.validated_data["storage_used_mb"]

    Kiosk.objects.filter(kiosk_id=kiosk.kiosk_id).update(**update_data)

    # Log the heartbeat
    DeviceLog.log(
        kiosk=kiosk,
        level="INFO",
        message="Heartbeat received",
        metadata={
            "battery_level": update_data.get("battery_level"),
            "storage_used_mb": update_data.get("storage_used_mb"),
            "firmware_version": update_data.get("firmware_version"),
        },
    )

    return Response(
        {"status": "ok", "kiosk_id": kiosk.kiosk_id, "timestamp": timezone.now()}
    )


@api_view(["POST"])
@authentication_classes([KioskJWTAuthentication])
@permission_classes([IsAuthenticated])
def kiosk_log(request):
    """
    Kiosk logging endpoint - devices can send log messages.
    Supports bulk logging for efficiency.

    Fortune 500 pattern:
    - Authentication: KioskJWTAuthentication (validates JWT contains kiosk)
    - Permission: IsAuthenticated (standard DRF permission)
    - request.user contains authenticated Kiosk object
    """
    # Get authenticated kiosk from request.user (set by KioskJWTAuthentication)
    kiosk = request.user

    # Security check: Ensure request.user is actually a Kiosk (not a User)
    if not isinstance(kiosk, Kiosk):
        return Response(
            {'detail': 'Authentication credentials are not valid for kiosk endpoints'},
            status=status.HTTP_403_FORBIDDEN
        )

    logs_data = request.data.get("logs", [])

    if not logs_data:
        return Response(
            {"error": "logs are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Create log entries
    log_entries = []
    for log_data in logs_data:
        log_entries.append(
            DeviceLog(
                kiosk=kiosk,
                log_level=log_data.get("level", "INFO"),
                message=log_data.get("message", ""),
                metadata=log_data.get("metadata", {}),
                timestamp=log_data.get("timestamp")
                or timezone.now(),  # Explicitly set timestamp
            )
        )

    DeviceLog.objects.bulk_create(log_entries)

    return Response(
        {"status": "ok", "logged_count": len(log_entries), "kiosk_id": kiosk.kiosk_id}
    )


class DeviceLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only ViewSet for device logs"""

    queryset = DeviceLog.objects.select_related("kiosk").order_by("-timestamp")
    serializer_class = DeviceLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["kiosk", "log_level", "timestamp"]

    def get_queryset(self):
        """Filter logs based on user permissions"""
        queryset = super().get_queryset()

        if hasattr(self.request.user, "role"):
            if self.request.user.role == "school_admin":
                # School admins can see all logs
                pass
            else:
                # Other users can only see logs from kiosks they have access to
                # This would need more complex permission logic
                pass

        return queryset

    @action(detail=False, methods=["get"], url_path="summary")
    def logs_summary(self, request):
        """Get logs summary by level and time"""
        # Group logs by level for the last 24 hours
        yesterday = timezone.now() - timedelta(days=1)

        summary = (
            DeviceLog.objects.filter(timestamp__gte=yesterday)
            .values("log_level")
            .annotate(count=Count("log_id"))
            .order_by("log_level")
        )

        return Response({"period": "last 24 hours", "summary": list(summary)})
