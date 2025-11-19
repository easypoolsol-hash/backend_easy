import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from bus_kiosk_backend.core.authentication import CloudTasksAuthentication
from bus_kiosk_backend.permissions import IsApprovedParent, IsCloudTasksRequest
from notifications.models import FCMToken, Notification, NotificationPreference
from notifications.serializers import (
    FCMTokenDeleteSerializer,
    FCMTokenSerializer,
    NotificationPreferenceSerializer,
    NotificationProcessSerializer,
    NotificationSerializer,
)
from notifications.services import get_notification_service

logger = logging.getLogger(__name__)


class ParentNotificationViewSet(viewsets.ViewSet):
    """
    ViewSet for parent notification management.

    Google Authorization Pattern:
    - Infrastructure APIs (FCM tokens) → IsAuthenticated only
    - Business APIs (notifications, preferences) → IsApprovedParent required

    Permissions are set per-action in get_permissions().
    """

    # Default permission (overridden per action)
    permission_classes = [IsAuthenticated, IsApprovedParent]

    def get_permissions(self):
        """
        Google IAM Pattern: Infrastructure vs Business permissions.

        Infrastructure (device management) - Authenticated only:
        - manage_fcm_token: Device identifier, not business data

        Business (sensitive data) - Approved parent required:
        - notification_preferences: Business feature toggles
        - list_notifications: Sensitive student data
        - mark_as_read: Notification tracking
        """
        if self.action == "manage_fcm_token":
            # Infrastructure: Any authenticated user can manage device tokens
            return [IsAuthenticated()]
        # Business: Requires approved parent
        return [IsAuthenticated(), IsApprovedParent()]

    @action(detail=False, methods=["post", "delete"], url_path="fcm-tokens")
    def manage_fcm_token(self, request):
        """
        Manage FCM tokens for push notifications.
        POST /api/v1/parents/me/fcm-tokens/ - Register token
        DELETE /api/v1/parents/me/fcm-tokens/ - Delete token

        Google Pattern: Infrastructure operation - works for authenticated users.
        Parent may have "pending" approval status - that's OK for device management.
        """
        if request.method == "POST":
            # Register FCM token
            serializer = FCMTokenSerializer(data=request.data, context={"request": request})
            if serializer.is_valid():
                fcm_token = serializer.save()
                logger.info(f"FCM token registered for parent {fcm_token.parent.parent_id} (approval_status={fcm_token.parent.approval_status})")
                return Response({"message": "FCM token registered successfully"}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        elif request.method == "DELETE":
            # Delete FCM token (user opt-out)
            # Google Pattern: This is for explicit opt-out, NOT called on normal logout
            if not hasattr(request.user, "parent_profile") or not request.user.parent_profile:
                return Response({"error": "Parent profile not found"}, status=status.HTTP_400_BAD_REQUEST)

            parent = request.user.parent_profile

            serializer = FCMTokenDeleteSerializer(data=request.data)
            if serializer.is_valid():
                token = serializer.validated_data["token"]
                deleted_count, _ = FCMToken.objects.filter(parent=parent, token=token).delete()

                if deleted_count > 0:
                    logger.info(f"FCM token deleted for parent {parent.parent_id}")
                    return Response({"message": "FCM token deleted successfully"}, status=status.HTTP_200_OK)
                return Response({"error": "Token not found"}, status=status.HTTP_404_NOT_FOUND)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get", "patch"], url_path="notification-preferences")
    def notification_preferences(self, request):
        """
        Get or update notification preferences.
        GET/PATCH /api/v1/parents/me/notification-preferences/
        """
        parent = request.user.parent_profile

        # Get or create preferences
        preferences, _created = NotificationPreference.objects.get_or_create(parent=parent)

        if request.method == "GET":
            serializer = NotificationPreferenceSerializer(preferences)
            return Response(serializer.data)

        # PATCH
        serializer = NotificationPreferenceSerializer(preferences, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Notification preferences updated for parent {parent.parent_id}")
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"], url_path="notifications")
    def list_notifications(self, request):
        """
        List all notifications for the parent.
        GET /api/v1/parents/me/notifications/
        """
        parent = request.user.parent_profile
        notifications = Notification.objects.filter(parent=parent).order_by("-created_at")[:100]
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="read")
    def mark_as_read(self, request, pk=None):
        """
        Mark a notification as read.
        POST /api/v1/parents/me/notifications/{notification_id}/read/
        """
        parent = request.user.parent_profile

        try:
            notification = Notification.objects.get(notification_id=pk, parent=parent)
        except Notification.DoesNotExist:
            return Response({"error": "Notification not found"}, status=status.HTTP_404_NOT_FOUND)

        notification.mark_as_read()
        return Response({"message": "Notification marked as read"})


class NotificationProcessView(APIView):
    """
    Internal endpoint for Cloud Tasks to process notifications.

    Authentication Flow (Google Cloud IAM Pattern):
    1. Cloud Tasks sends request with OIDC token
    2. Cloud Run validates token via IAM (roles/run.invoker)
    3. CloudTasksAuthentication identifies request via headers
    4. IsCloudTasksRequest permission explicitly allows

    This is the Fortune 500 / Google-recommended explicit authentication pattern.
    No bypass - every request is authenticated and authorized explicitly.
    """

    # Explicit authentication - Cloud Tasks only
    authentication_classes = [CloudTasksAuthentication]

    # Explicit permission - only CloudTasksUser allowed
    permission_classes = [IsCloudTasksRequest]

    def post(self, request):
        """
        Process a queued notification.
        POST /api/v1/notifications/process/
        Called by Cloud Tasks.
        """
        try:
            serializer = NotificationProcessSerializer(data=request.data)
            if not serializer.is_valid():
                logger.error(f"Invalid notification data: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            notification_id = serializer.validated_data["notification_id"]

            # Request is authenticated as CloudTasksUser
            # Cloud Run IAM has already validated the OIDC token
            logger.info(f"Processing notification {notification_id} from task={request.user.task_name}")

            success = get_notification_service().process_notification(notification_id)

            if success:
                logger.info(f"Notification {notification_id} sent successfully")
                return Response({"status": "sent"})
            else:
                logger.warning(f"Notification {notification_id} failed to send")
                # Return 200 to prevent Cloud Tasks from retrying on permanent failures
                # The notification status is updated in the database
                return Response({"status": "failed"})

        except Exception as e:
            logger.error(f"Unexpected error processing notification: {e}", exc_info=True)
            # Return 500 to trigger Cloud Tasks retry for transient errors
            return Response({"error": "Internal server error processing notification"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
