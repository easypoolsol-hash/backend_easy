"""
Unit tests for Notification Service

Tests notification creation, queuing, and processing in isolation.
Uses mocking for external services (Cloud Tasks, FCM).
Follows Google testing patterns with pytest.param for clear test IDs.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from notifications.services import NotificationService
from tests.factories import (
    FCMTokenFactory,
    NotificationFactory,
    ParentFactory,
    StudentFactory,
    StudentParentFactory,
)


@pytest.mark.django_db
class TestNotificationService:
    """Tests for NotificationService methods"""

    def test_create_boarding_notification_success(self):
        """Create notification and queue to Cloud Tasks"""
        # Arrange
        parent = ParentFactory()
        student = StudentFactory()
        StudentParentFactory(student=student, parent=parent)

        service = NotificationService()

        # Act
        with patch.object(service.cloud_task_service, "queue_notification", return_value=True):
            notifications = service.create_boarding_notification(
                student=student,
                event_type="boarding",
                timestamp=datetime.fromisoformat("2025-11-19T21:30:00+05:30"),
                bus_route="test-route-123",
            )

        # Assert - returns list of notifications (one per parent)
        assert len(notifications) == 1
        notification = notifications[0]
        assert notification.status == "queued"
        assert notification.parent == parent
        assert notification.student == student
        assert "boarded" in notification.title.lower()

    def test_create_notification_respects_preferences(self):
        """Skip notification if parent has disabled this type"""
        # Arrange
        parent = ParentFactory()
        student = StudentFactory()
        StudentParentFactory(student=student, parent=parent)

        # Disable boarding notifications
        from notifications.models import NotificationPreference

        NotificationPreference.objects.create(
            parent=parent,
            boarding=False,  # Disabled
        )

        service = NotificationService()

        # Act
        notifications = service.create_boarding_notification(
            student=student,
            event_type="boarding",
            timestamp=datetime.fromisoformat("2025-11-19T21:30:00+05:30"),
        )

        # Assert - returns empty list when preferences disabled
        assert notifications == []

    @pytest.mark.parametrize(
        "initial_status,expected_after_send",
        [
            pytest.param("queued", "sent", id="queued_to_sent"),
            pytest.param("pending", "sent", id="pending_to_sent"),
        ],
    )
    def test_process_notification_status_transitions(self, initial_status, expected_after_send):
        """Process notification updates status to sent"""
        # Arrange
        parent = ParentFactory()
        FCMTokenFactory(parent=parent)  # Parent has FCM token

        notification = NotificationFactory(parent=parent, status=initial_status)

        service = NotificationService()

        # Act
        with patch.object(service.fcm_service, "send_to_parent", return_value=True):
            success = service.process_notification(str(notification.notification_id))

        # Assert
        assert success is True
        notification.refresh_from_db()
        assert notification.status == expected_after_send
        assert notification.sent_at is not None

    def test_process_notification_marks_failed_on_fcm_error(self):
        """Mark notification as failed when FCM send fails"""
        # Arrange
        parent = ParentFactory()
        FCMTokenFactory(parent=parent)

        notification = NotificationFactory(parent=parent, status="queued")

        service = NotificationService()

        # Act
        with patch.object(service.fcm_service, "send_to_parent", return_value=False):
            success = service.process_notification(str(notification.notification_id))

        # Assert
        assert success is False
        notification.refresh_from_db()
        assert notification.status == "failed"

    def test_process_notification_skips_already_sent(self):
        """Skip processing if notification already sent"""
        # Arrange
        notification = NotificationFactory(status="sent")

        service = NotificationService()

        # Act
        success = service.process_notification(str(notification.notification_id))

        # Assert
        assert success is True  # Returns True but doesn't reprocess

    def test_process_notification_not_found(self):
        """Handle missing notification gracefully"""
        # Arrange
        service = NotificationService()

        # Act
        success = service.process_notification("nonexistent-notification-id")

        # Assert
        assert success is False


@pytest.mark.django_db
class TestCloudTaskService:
    """Tests for Cloud Task queuing"""

    def test_queue_notification_creates_task(self):
        """Queue notification creates Cloud Task with correct payload"""
        # Arrange
        notification = NotificationFactory()

        from notifications.services import CloudTaskService

        service = CloudTaskService()

        # Act
        with patch.object(service, "client") as mock_client:
            mock_client.create_task.return_value = MagicMock(name="test-task")
            success = service.queue_notification(str(notification.notification_id))

        # Assert
        assert success is True
        mock_client.create_task.assert_called_once()

        # Verify task payload
        call_args = mock_client.create_task.call_args
        task = call_args.kwargs.get("task") or call_args[1].get("task")
        assert "notification_id" in str(task)


@pytest.mark.django_db
class TestFCMService:
    """Tests for FCM push notification sending"""

    def test_send_to_parent_with_token(self):
        """Send FCM notification to parent with registered token"""
        # Arrange
        parent = ParentFactory()
        FCMTokenFactory(parent=parent, token="test_fcm_token_123")
        notification = NotificationFactory(parent=parent)

        from notifications.services import FCMService

        service = FCMService()

        # Act - mock send_each_for_multicast (what the service actually uses)
        with patch("firebase_admin.messaging.send_each_for_multicast") as mock_send:
            mock_response = MagicMock()
            mock_response.success_count = 1
            mock_response.failure_count = 0
            mock_response.responses = []
            mock_send.return_value = mock_response
            success = service.send_to_parent(parent, notification)

        # Assert
        assert success is True
        mock_send.assert_called_once()

    def test_send_to_parent_no_tokens(self):
        """Return False when parent has no FCM tokens"""
        # Arrange
        parent = ParentFactory()
        # No FCMToken created
        notification = NotificationFactory(parent=parent)

        from notifications.services import FCMService

        service = FCMService()

        # Act
        success = service.send_to_parent(parent, notification)

        # Assert
        assert success is False

    def test_send_to_parent_handles_fcm_error(self):
        """Handle FCM API errors gracefully"""
        # Arrange
        parent = ParentFactory()
        FCMTokenFactory(parent=parent)
        notification = NotificationFactory(parent=parent)

        from notifications.services import FCMService

        service = FCMService()

        # Act
        with patch("firebase_admin.messaging.send_each_for_multicast") as mock_send:
            mock_send.side_effect = Exception("FCM API error")
            success = service.send_to_parent(parent, notification)

        # Assert
        assert success is False
