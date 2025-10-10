"""
End-to-end tests for complete kiosk workflow (Essential tests only)

Tests the full flow: Auth → Heartbeat → Log
"""

from django.utils import timezone
import pytest
from rest_framework import status


@pytest.mark.django_db
class TestKioskWorkflow:
    """Essential end-to-end kiosk workflow test"""

    def test_complete_kiosk_workflow(self, api_client, test_kiosk, openapi_helper):
        """
        Test complete kiosk workflow:
        1. Activate with kiosk_id + activation_token
        2. Get JWT token
        3. Send heartbeat
        4. Send log
        """
        kiosk, activation_token = test_kiosk

        # Step 1: Activate kiosk
        auth_response = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )

        assert auth_response.status_code == status.HTTP_200_OK
        assert "access" in auth_response.data
        token = auth_response.data["access"]

        # Step 2: Send heartbeat with token
        from django.utils import timezone

        from kiosks.models import KioskStatus

        # Create KioskStatus for heartbeat
        KioskStatus.objects.create(kiosk=kiosk, last_heartbeat=timezone.now())

        heartbeat_response = api_client.post(
            openapi_helper(operation_id="kiosk_heartbeat", kiosk_id=kiosk.kiosk_id),
            {
                "timestamp": timezone.now().isoformat(),
                "database_version": timezone.now().isoformat(),
                "database_hash": "abc123def456",
                "student_count": 1,
                "embedding_count": 1,
                "battery_level": 90.0,
                "storage_available_mb": 1024,
                "last_face_scan": timezone.now().isoformat(),
            },
            HTTP_AUTHORIZATION=f"Bearer {token}",
            format="json",
        )

        assert heartbeat_response.status_code == status.HTTP_204_NO_CONTENT

        # Step 3: Send device log with token
        log_response = api_client.post(
            openapi_helper(operation_id="kiosk_log"),
            {
                "logs": [
                    {
                        "level": "INFO",
                        "message": "Kiosk started successfully",
                        "metadata": {
                            "version": "1.0.0",
                            "kiosk_id": str(kiosk.kiosk_id),
                        },
                    }
                ]
            },
            HTTP_AUTHORIZATION=f"Bearer {token}",
            format="json",
        )

        assert log_response.status_code == status.HTTP_200_OK
        assert log_response.data["status"] == "ok"
        assert log_response.data["logged_count"] == 1

    def test_snapshot_download_workflow(self, api_client, test_kiosk, openapi_helper):
        """
        Test the complete snapshot download workflow:
        1. Activate kiosk to get JWT token.
        2. Call /check-updates to simulate a client check.
        3. Call /download-snapshot to get the database file.
        4. Verify the response is a valid file download.
        """
        kiosk, activation_token = test_kiosk

        # Step 1: Activate kiosk
        auth_response = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        token = auth_response.data["access"]

        # Step 2: Check for updates (optional, but good practice to test)
        check_updates_response = api_client.get(
            openapi_helper(operation_id="kiosk_check_updates", kiosk_id=kiosk.kiosk_id),
            {"last_sync": timezone.now().isoformat()},
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert check_updates_response.status_code == status.HTTP_200_OK

        # Step 3: Download the snapshot
        snapshot_response = api_client.get(
            openapi_helper(operation_id="kiosk_download_snapshot", kiosk_id=kiosk.kiosk_id),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        # Step 4: Verify the file response
        assert snapshot_response.status_code == status.HTTP_200_OK
        assert snapshot_response["Content-Type"] == "application/x-sqlite3"
        assert "attachment; filename=" in snapshot_response["Content-Disposition"]

        # Verify the content is a valid SQLite file by checking the header
        assert snapshot_response.content.startswith(b"SQLite format 3\x00")

    def test_workflow_fails_without_authentication(self, api_client, test_kiosk, openapi_helper):
        """Test workflow fails if kiosk doesn't authenticate first"""
        kiosk, _ = test_kiosk

        # Try heartbeat without auth
        response = api_client.post(
            openapi_helper(operation_id="kiosk_heartbeat", kiosk_id=kiosk.kiosk_id),
            {"kiosk_id": kiosk.kiosk_id, "battery_level": 90},
            format="json",
        )

        # DRF returns 401 Unauthorized when authentication is missing
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
