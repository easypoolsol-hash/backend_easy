"""
Integration tests for Notification API endpoints

Tests real HTTP requests through the full Django stack.
Tests Cloud Tasks authentication pattern (Google IAM).
Uses pytest.param for better test readability.
"""

from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from tests.factories import (
    FCMTokenFactory,
    NotificationFactory,
    ParentFactory,
    StudentFactory,
    StudentParentFactory,
)


@pytest.mark.django_db
class TestNotificationProcessEndpoint:
    """Tests for POST /api/v1/notifications/process/ (Cloud Tasks)"""

    def test_cloud_tasks_request_success(self):
        """Cloud Tasks request with proper headers succeeds"""
        # Arrange
        parent = ParentFactory()
        FCMTokenFactory(parent=parent)
        notification = NotificationFactory(parent=parent, status="queued")

        client = APIClient()

        # Act - Simulate Cloud Tasks request with headers
        with patch("notifications.services.notification_service.fcm_service.send_to_parent", return_value=True):
            response = client.post(
                "/api/v1/notifications/process/",
                data={"notification_id": str(notification.notification_id)},
                format="json",
                # Cloud Tasks headers (set by Cloud Run after OIDC validation)
                HTTP_X_CLOUDTASKS_TASKNAME="task-123",
                HTTP_X_CLOUDTASKS_QUEUENAME="projects/easypool-backend/locations/asia-south1/queues/notifications-queue-dev",
                HTTP_X_CLOUDTASKS_TASKRETRYCOUNT="0",
            )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "sent"

        # Verify notification was processed
        notification.refresh_from_db()
        assert notification.status == "sent"

    def test_request_without_cloud_tasks_headers_denied(self):
        """Request without Cloud Tasks headers is denied"""
        # Arrange
        notification = NotificationFactory(status="queued")
        client = APIClient()

        # Act - Regular request without Cloud Tasks headers
        response = client.post(
            "/api/v1/notifications/process/",
            data={"notification_id": str(notification.notification_id)},
            format="json",
        )

        # Assert - Should be forbidden (no Cloud Tasks auth)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_request_with_wrong_queue_denied(self):
        """Request from unexpected queue is denied"""
        # Arrange
        notification = NotificationFactory(status="queued")
        client = APIClient()

        # Act - Cloud Tasks headers from wrong queue
        response = client.post(
            "/api/v1/notifications/process/",
            data={"notification_id": str(notification.notification_id)},
            format="json",
            HTTP_X_CLOUDTASKS_TASKNAME="task-456",
            HTTP_X_CLOUDTASKS_QUEUENAME="projects/other-project/queues/wrong-queue",
        )

        # Assert - Should fail authentication (wrong queue)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_authenticated_user_cannot_access(self, approved_parent_client):
        """Regular authenticated users cannot access Cloud Tasks endpoint"""
        # Arrange
        client, _user, _parent = approved_parent_client
        notification = NotificationFactory(status="queued")

        # Act - Authenticated user trying to access
        response = client.post(
            "/api/v1/notifications/process/",
            data={"notification_id": str(notification.notification_id)},
            format="json",
        )

        # Assert - Should be forbidden (not Cloud Tasks)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_invalid_notification_id(self):
        """Handle invalid notification ID gracefully"""
        # Arrange
        client = APIClient()

        # Act
        with patch("notifications.services.FCMService.send_to_parent", return_value=False):
            response = client.post(
                "/api/v1/notifications/process/",
                data={"notification_id": "nonexistent-id"},
                format="json",
                HTTP_X_CLOUDTASKS_TASKNAME="task-789",
                HTTP_X_CLOUDTASKS_QUEUENAME="projects/easypool-backend/locations/asia-south1/queues/notifications-queue-dev",
            )

        # Assert - Should return 200 with failed status (prevent retries)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "failed"


@pytest.mark.django_db
class TestParentNotificationEndpoints:
    """Tests for parent notification management endpoints"""

    def test_register_fcm_token_success(self, approved_parent_client):
        """Approved parent can register FCM token"""
        # Arrange
        client, _user, _parent = approved_parent_client

        # Act
        response = client.post(
            "/api/v1/parents/me/fcm-tokens/",
            data={"token": "new_fcm_token_12345", "device_type": "android"},
            format="json",
        )

        # Assert
        assert response.status_code == status.HTTP_201_CREATED

    def test_list_notifications_success(self, approved_parent_client):
        """Approved parent can list their notifications"""
        # Arrange
        client, _user, parent = approved_parent_client

        # Create some notifications for this parent
        NotificationFactory(parent=parent)
        NotificationFactory(parent=parent)

        # Act
        response = client.get("/api/v1/parents/me/notifications/")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_mark_notification_as_read(self, approved_parent_client):
        """Approved parent can mark notification as read"""
        # Arrange
        client, _user, parent = approved_parent_client
        notification = NotificationFactory(parent=parent, status="sent")

        # Act
        response = client.post(
            f"/api/v1/parents/me/notifications/{notification.notification_id}/read/",
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        notification.refresh_from_db()
        assert notification.status == "read"

    def test_unapproved_parent_cannot_access(self, unapproved_parent_client):
        """Unapproved parent cannot access notification endpoints"""
        # Arrange
        client, _user, _parent = unapproved_parent_client

        # Act
        response = client.get("/api/v1/parents/me/notifications/")

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_notification_preferences(self, approved_parent_client):
        """Approved parent can get notification preferences"""
        # Arrange
        client, _user, _parent = approved_parent_client

        # Act
        response = client.get("/api/v1/parents/me/notification-preferences/")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert "boarding" in response.data
        assert "deboarding" in response.data

    def test_update_notification_preferences(self, approved_parent_client):
        """Approved parent can update notification preferences"""
        # Arrange
        client, _user, _parent = approved_parent_client

        # Act
        response = client.patch(
            "/api/v1/parents/me/notification-preferences/",
            data={"boarding": False, "quiet_hours_enabled": True},
            format="json",
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data["boarding"] is False
        assert response.data["quiet_hours_enabled"] is True
