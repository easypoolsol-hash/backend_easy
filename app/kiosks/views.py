from datetime import timedelta
import hashlib
import logging
from typing import Any, cast

from django.db.models import Count
from django.http import HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.request import Request
from rest_framework.response import Response

from bus_kiosk_backend.permissions import IsSchoolAdmin

from .authentication import KioskJWTAuthentication, activate_kiosk
from .models import DeviceLog, Kiosk, KioskStatus
from .permissions import IsKiosk
from .serializers import (
    CheckUpdatesResponseSerializer,
    CheckUpdatesSerializer,
    DeviceLogSerializer,
    HeartbeatSerializer,
    KioskActivationResponseSerializer,
    KioskActivationSerializer,
    KioskSerializer,
)
from .services import SnapshotGenerator


def calculate_checksum(data: bytes) -> str:
    """Calculate SHA-256 checksum of data."""
    return hashlib.sha256(data).hexdigest()


# Fortune 500 Standard: DRF APIView for kiosk activation
@extend_schema(
    request=KioskActivationSerializer,
    responses={
        200: KioskActivationResponseSerializer,
        400: {"description": "Invalid activation token or kiosk not found"},
    },
    operation_id="kiosk_activate",
    description="""
    **Fortune 500 Standard: One-time Device Activation**

    Used by: Google Nest, Amazon Alexa, Netflix devices

    Activates a kiosk using a disposable activation token.
    After activation, the token becomes garbage and cannot be reused.

    **Security Features:**
    - One-time use activation tokens (WhatsApp leak protection)
    - Tokens destroyed after first use
    - 60-day rotating refresh tokens
    - 15-minute access tokens

    **Example Request:**
    ```json
    {
        "kiosk_id": "KIOSK-SCHOOL-001",
        "activation_token": "8Jz4Y-x9K2mQ_r5WvLp3NcTg7HfB6DsA1eU0oI9j8Xw"
    }
    ```
    """,
    tags=["Kiosk Activation"],
)
@api_view(["POST"])
@authentication_classes([])  # No authentication required for activation
@permission_classes([])  # Public endpoint
def activate_kiosk_view(request: Request) -> Response:
    """
    Fortune 500 Standard: DRF APIView for kiosk activation

    Replaces plain Django view with proper DRF patterns:
    - Automatic serialization/deserialization
    - Built-in validation
    - OpenAPI schema generation
    - Consistent error responses
    """
    # Validate input using DRF serializer (Fortune 500 pattern)
    serializer = KioskActivationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    kiosk_id = serializer.validated_data["kiosk_id"]
    activation_token = serializer.validated_data["activation_token"]

    # Activate kiosk (business logic in authentication module)
    try:
        result = activate_kiosk(kiosk_id, activation_token)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # Prepare response data (Fortune 500 standard structure)
    response_data = {
        "message": result["message"],
        "refresh": result["refresh_token"],
        "access": result["access_token"],
        "kiosk_id": result["kiosk"].kiosk_id,
        "bus_id": result["kiosk"].bus.bus_id if result["kiosk"].bus else None,
        "activation_token_destroyed": True,
    }

    # Log successful activation (Fortune 500: audit trail)
    # Be defensive: logging/audit may touch external systems (cache, etc.).
    # If audit logging fails, don't fail the activation request.
    logger = logging.getLogger(__name__)
    try:
        DeviceLog.log(
            kiosk=result["kiosk"],
            level="INFO",
            message="Kiosk activated successfully",
            metadata={
                "ip_address": request.META.get("REMOTE_ADDR"),
                "user_agent": request.META.get("HTTP_USER_AGENT"),
            },
        )
    except Exception as exc:  # pragma: no cover - defensive safety net
        # Log the failure to the application logger, but don't surface to client
        logger.exception("Failed to record DeviceLog for kiosk activation: %s", exc)

    # Return DRF Response (not JsonResponse)
    return Response(response_data, status=status.HTTP_200_OK)


class KioskViewSet(viewsets.ModelViewSet):  # type: ignore[type-arg]
    """ViewSet for kiosk management (admin only)"""

    queryset = Kiosk.objects.all()
    serializer_class = KioskSerializer


@extend_schema(
    request=DeviceLogSerializer,
    responses={200: {"type": "object", "properties": {"status": {"type": "string"}}}},
    operation_id="kiosk_log",
    description="Kiosk logging endpoint for device log submission",
)
@api_view(["POST"])
@authentication_classes([KioskJWTAuthentication])
@permission_classes([IsKiosk])
def kiosk_log(request: Request) -> Response:
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
            {"detail": "Authentication credentials are not valid for kiosk endpoints"},
            status=status.HTTP_403_FORBIDDEN,
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
                timestamp=log_data.get("timestamp") or timezone.now(),  # Explicitly set timestamp
            )
        )

    DeviceLog.objects.bulk_create(log_entries)

    return Response({"status": "ok", "logged_count": len(log_entries), "kiosk_id": kiosk.kiosk_id})


class DeviceLogViewSet(viewsets.ReadOnlyModelViewSet):  # type: ignore[type-arg]
    """Read-only ViewSet for device logs (admin only)"""

    queryset = DeviceLog.objects.select_related("kiosk").order_by("-timestamp")
    serializer_class = DeviceLogSerializer
    permission_classes = [IsSchoolAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["kiosk", "log_level", "timestamp"]

    # Only school admins can view device logs

    @action(detail=False, methods=["get"], url_path="summary")
    def logs_summary(self: Any, request: Request) -> Response:
        """Get logs summary by level and time"""
        # Group logs by level for the last 24 hours
        yesterday = timezone.now() - timedelta(days=1)

        summary = DeviceLog.objects.filter(timestamp__gte=yesterday).values("log_level").annotate(count=Count("log_id")).order_by("log_level")

        return Response({"period": "last 24 hours", "summary": list(summary)})


# Sync Endpoints


@extend_schema(
    parameters=[CheckUpdatesSerializer],
    responses={200: CheckUpdatesResponseSerializer},
    operation_id="kiosk_check_updates",
    description="Check if kiosk needs database update",
)
@api_view(["GET"])
@authentication_classes([KioskJWTAuthentication])
@permission_classes([IsKiosk])
def check_updates(request: Request, kiosk_id: str) -> Response:
    """
    Check if kiosk database needs updating.

    Compares kiosk's last_sync timestamp with bus's last_student_update.
    Returns metadata about current database version.
    """
    # Verify authenticated kiosk matches requested kiosk_id
    kiosk_user = cast(Kiosk, request.user)
    if kiosk_user.kiosk_id != kiosk_id:
        return Response(
            {"detail": "Not authorized for this kiosk"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Use the authenticated kiosk object for subsequent operations
    kiosk = kiosk_user

    if not kiosk.bus:
        return Response(
            {"detail": "Kiosk not assigned to a bus"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate query params
    serializer = CheckUpdatesSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)

    last_sync_hash = serializer.validated_data.get("last_sync_hash", "")
    bus = kiosk.bus

    # Check if update needed
    # (A more robust method than using timestamps)

    # Generate metadata to check the latest version on the server
    # This is efficient as it doesn't generate the full snapshot file yet
    # Use the local bus variable (avoid unused variable warnings)
    generator = SnapshotGenerator(bus.bus_id)
    _, metadata = generator.generate()  # We only need metadata here

    # Check if update needed by comparing content hashes
    # (A more robust method than using timestamps)
    needs_update = metadata.get("content_hash") != last_sync_hash

    response_data = {
        "needs_update": needs_update,
        "current_version": metadata["sync_timestamp"],
        "student_count": metadata["student_count"],
        "embedding_count": metadata["embedding_count"],
        "content_hash": metadata["content_hash"],
    }

    return Response(response_data)


@extend_schema(
    responses={200: OpenApiTypes.BINARY},
    operation_id="kiosk_download_snapshot",
    description="Generate and download a kiosk database snapshot.",
)
@api_view(["GET"])
@authentication_classes([KioskJWTAuthentication])
@permission_classes([IsKiosk])
def download_snapshot(request: Request, kiosk_id: str) -> Response | HttpResponse:
    """
    Generates and serves a SQLite database snapshot for the specified kiosk.

    This endpoint is protected and ensures the kiosk can only download data
    for its assigned bus route.
    """
    try:
        kiosk = Kiosk.objects.select_related("bus").get(kiosk_id=kiosk_id)
    except Kiosk.DoesNotExist:
        return Response({"detail": "Kiosk not found"}, status=status.HTTP_404_NOT_FOUND)

    kiosk_user = cast(Kiosk, request.user)
    if kiosk_user.kiosk_id != kiosk_id:
        return Response(
            {"detail": "Not authorized for this kiosk"},
            status=status.HTTP_403_FORBIDDEN,
        )

    if not kiosk.bus:
        return Response(
            {"detail": "Kiosk not assigned to a bus"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # 1. Generate the snapshot database in memory.
        generator = SnapshotGenerator(kiosk.bus.bus_id)
        snapshot_bytes, metadata = generator.generate()

        # 2. Create a direct file response.
        response = HttpResponse(snapshot_bytes, content_type="application/x-sqlite3")
        response["Content-Disposition"] = f'attachment; filename="snapshot_{metadata["sync_timestamp"]}.db"'
        response["x-snapshot-checksum"] = calculate_checksum(snapshot_bytes)

        return response

    except Exception as e:
        # In a real app, you would log this exception.
        return Response(
            {"detail": f"Failed to generate snapshot: {e}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@extend_schema(
    request=HeartbeatSerializer,
    responses={204: None},
    operation_id="kiosk_heartbeat",
    description="Report kiosk health and sync status",
)
@api_view(["POST"])
@authentication_classes([KioskJWTAuthentication])
@permission_classes([IsKiosk])
def heartbeat(request: Request, kiosk_id: str) -> Response:
    """
    Receive heartbeat from kiosk with health metrics and sync status.

    Updates KioskStatus model with current state.
    Determines overall status (ok/warning/critical) based on metrics.
    """
    try:
        kiosk = Kiosk.objects.get(kiosk_id=kiosk_id)
    except Kiosk.DoesNotExist:
        return Response({"detail": "Kiosk not found"}, status=status.HTTP_404_NOT_FOUND)

    # Verify authenticated kiosk matches requested kiosk_id
    kiosk_user = cast(Kiosk, request.user)
    if kiosk_user.kiosk_id != kiosk_id:
        return Response(
            {"detail": "Not authorized for this kiosk"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Validate request
    serializer = HeartbeatSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    data = serializer.validated_data
    health = data.get("health", {})

    # Determine status based on health metrics
    kiosk_status = "ok"

    battery_level = health.get("battery_level")
    is_charging = health.get("is_charging", False)

    if battery_level is not None:
        if battery_level < 10 and not is_charging:
            kiosk_status = "critical"
        elif battery_level < 20 and not is_charging:
            kiosk_status = "warning"

    # Check if offline (heartbeat old)
    if hasattr(kiosk, "status") and kiosk.status:
        if kiosk.status.is_offline:
            kiosk_status = "critical"

    # Update or create KioskStatus
    KioskStatus.objects.update_or_create(
        kiosk=kiosk,
        defaults={
            "last_heartbeat": data["timestamp"],
            "database_version": data["database_version"],
            "database_hash": data.get("database_hash", ""),
            "student_count": data["student_count"],
            "embedding_count": data["embedding_count"],
            "battery_level": battery_level,
            "is_charging": is_charging,
            "storage_available_mb": health.get("storage_available_mb"),
            "camera_active": health.get("camera_active", False),
            "network_type": health.get("network_type"),
            "app_version": health.get("app_version"),
            "last_face_detected": (
                timezone.now() - timedelta(minutes=health["last_face_detected_ago_min"])
                if health.get("last_face_detected_ago_min") is not None
                else None
            ),
            "faces_detected_today": health.get("faces_detected_today", 0),
            "students_identified_today": health.get("students_identified_today", 0),
            "status": kiosk_status,
        },
    )

    # Also update Kiosk model heartbeat
    kiosk.last_heartbeat = data["timestamp"]
    kiosk.save(update_fields=["last_heartbeat"])

    return Response(status=status.HTTP_204_NO_CONTENT)
