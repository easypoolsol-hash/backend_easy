import json
import logging

from django.conf import settings
from firebase_admin import messaging
from google.cloud import tasks_v2

from notifications.models import FCMToken, Notification, NotificationPreference
from students.models import Parent, Student

logger = logging.getLogger(__name__)


class CloudTaskService:
    """Service to queue notifications via Google Cloud Tasks."""

    def __init__(self):
        self.client = tasks_v2.CloudTasksClient()
        self.queue_path = self.client.queue_path(
            project=settings.GCP_PROJECT_ID,
            location=settings.GCP_REGION,
            queue=settings.CLOUD_TASKS_QUEUE_NAME,
        )

    def queue_notification(self, notification_id: str) -> bool:
        """
        Queue a notification for async processing.

        Args:
            notification_id: The notification ID to process

        Returns:
            True if queued successfully, False otherwise
        """
        try:
            # Build the task
            task = {
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": f"{settings.BACKEND_URL}/api/v1/notifications/process/",
                    "headers": {
                        "Content-Type": "application/json",
                    },
                    "body": json.dumps({"notification_id": notification_id}).encode(),
                    "oidc_token": {
                        "service_account_email": settings.CLOUD_TASKS_SERVICE_ACCOUNT,
                    },
                }
            }

            # Create the task
            response = self.client.create_task(parent=self.queue_path, task=task)
            logger.info(f"Queued notification task: {notification_id}, task: {response.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to queue notification {notification_id}: {e}")
            return False


class FCMService:
    """Service to send notifications via Firebase Cloud Messaging."""

    def send_to_parent(self, parent: Parent, notification: Notification) -> bool:
        """
        Send notification to all of a parent's devices.

        Args:
            parent: Parent model instance
            notification: Notification model instance

        Returns:
            True if at least one device received the notification
        """
        # Get all active FCM tokens for this parent
        tokens = list(FCMToken.objects.filter(parent=parent, is_active=True).values_list("token", flat=True))

        if not tokens:
            logger.warning(f"No FCM tokens for parent {parent.parent_id}")
            return False

        try:
            # Build the FCM message
            message = messaging.MulticastMessage(
                tokens=tokens,
                notification=messaging.Notification(
                    title=notification.title,
                    body=notification.body,
                ),
                data={
                    "notification_id": str(notification.notification_id),
                    "type": notification.notification_type,
                    **{k: str(v) for k, v in notification.data.items()},
                },
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(
                        channel_id="easypool_alerts",
                        priority="high",
                    ),
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            alert=messaging.ApsAlert(
                                title=notification.title,
                                body=notification.body,
                            ),
                            sound="default",
                            badge=1,
                        ),
                    ),
                ),
            )

            # Send the message
            response = messaging.send_each_for_multicast(message)

            # Handle failed tokens
            if response.failure_count > 0:
                self._handle_failed_tokens(tokens, response.responses)

            logger.info(f"FCM sent to {response.success_count}/{len(tokens)} devices for notification {notification.notification_id}")

            return response.success_count > 0

        except Exception as e:
            logger.error(f"FCM send failed for notification {notification.notification_id}: {e}")
            return False

    def _handle_failed_tokens(self, tokens: list, responses: list):
        """Mark invalid tokens as inactive."""
        for idx, response in enumerate(responses):
            if not response.success:
                error = response.exception
                # Check for registration errors (invalid/expired tokens)
                if isinstance(error, messaging.UnregisteredError):
                    FCMToken.objects.filter(token=tokens[idx]).update(is_active=False)
                    logger.info(f"Deactivated invalid FCM token: {tokens[idx][:20]}...")
                else:
                    logger.warning(f"FCM error for token {tokens[idx][:20]}...: {error}")


class NotificationService:
    """Main service to create and send notifications."""

    def __init__(self):
        self.cloud_task_service = CloudTaskService()
        self.fcm_service = FCMService()

    def create_boarding_notification(
        self,
        student: Student,
        event_type: str,
        timestamp,
        bus_route: str = "",
    ) -> list[Notification]:
        """
        Create notifications for all parents of a student when boarding/deboarding.

        Args:
            student: Student model instance
            event_type: 'boarding' or 'deboarding'
            timestamp: Event timestamp
            bus_route: Optional bus route name

        Returns:
            List of created Notification objects
        """
        notifications: list[Notification] = []

        # Get all parents for this student
        parents = student.get_parents()

        if not parents:
            logger.warning(f"No parents found for student {student.student_id}")
            return notifications

        # Build notification content
        student_name = student.encrypted_name
        time_str = timestamp.strftime("%I:%M %p")

        if event_type == "boarding":
            title = f"{student_name} boarded the bus"
            body = f"Your child boarded the bus at {time_str}"
        else:
            title = f"{student_name} dropped off"
            body = f"Your child was dropped off safely at {time_str}"

        # Create notification for each parent
        for parent in parents:
            # Check preferences
            try:
                prefs = parent.notification_preferences
                if not prefs.is_type_enabled(event_type):
                    logger.info(f"Parent {parent.parent_id} disabled {event_type} notifications")
                    continue
            except NotificationPreference.DoesNotExist:
                # Create default preferences if not exists
                NotificationPreference.objects.create(parent=parent)

            # Create notification record
            notification = Notification.objects.create(
                parent=parent,
                student=student,
                notification_type=event_type,
                title=title,
                body=body,
                data={
                    "student_id": str(student.student_id),
                    "bus_route": bus_route,
                    "event_time": timestamp.isoformat(),
                },
            )

            # Queue for delivery
            if self.cloud_task_service.queue_notification(str(notification.notification_id)):
                notification.mark_as_queued()
            else:
                notification.mark_as_failed("Failed to queue task")

            notifications.append(notification)

        return notifications

    def process_notification(self, notification_id: str) -> bool:
        """
        Process a queued notification (called by Cloud Tasks).

        Args:
            notification_id: The notification ID to process

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            notification = Notification.objects.select_related("parent").get(notification_id=notification_id)
        except Notification.DoesNotExist:
            logger.error(f"Notification not found: {notification_id}")
            return False

        # Check if already sent
        if notification.status in ("sent", "read"):
            logger.info(f"Notification {notification_id} already sent")
            return True

        # Send via FCM
        success = self.fcm_service.send_to_parent(notification.parent, notification)

        if success:
            notification.mark_as_sent()
            return True
        else:
            notification.mark_as_failed("FCM send failed")
            return False


# Singleton instances for easy import
cloud_task_service = CloudTaskService()
fcm_service = FCMService()
notification_service = NotificationService()
