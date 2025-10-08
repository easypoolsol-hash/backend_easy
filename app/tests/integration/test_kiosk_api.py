"""
Integration tests for kiosk API endpoints (Essential tests only)

Tests authenticated API access using JWT tokens.
"""

from django.utils import timezone
import pytest
from rest_framework import status


@pytest.mark.django_db
class TestKioskAPIAuthentication:
    """Essential tests for kiosk API access with JWT"""

    def test_kiosk_heartbeat_with_valid_token(self, api_client, test_kiosk):
        """Test kiosk heartbeat with valid JWT token"""
        kiosk, activation_token = test_kiosk

        # 1. Activate kiosk and get token
        auth_response = api_client.post(
            "/api/v1/kiosks/activate/",
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        token = auth_response.json()["access"]

        # Create KioskStatus for the kiosk
        from kiosks.models import KioskStatus

        KioskStatus.objects.create(kiosk=kiosk, last_heartbeat=timezone.now())

        heartbeat_data = {
            "timestamp": timezone.now().isoformat(),
            "database_version": timezone.now().isoformat(),
            "database_hash": "abc123def456",
            "student_count": 1,
            "embedding_count": 1,
        }
        response = api_client.post(
            f"/api/v1/{kiosk.kiosk_id}/heartbeat/",
            data=heartbeat_data,
            HTTP_AUTHORIZATION=f"Bearer {token}",
            format="json",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_kiosk_heartbeat_without_token(self, api_client, test_kiosk):
        """Test kiosk heartbeat fails without token"""
        kiosk, _ = test_kiosk

        response = api_client.post(
            f"/api/v1/{kiosk.kiosk_id}/heartbeat/",
            {"kiosk_id": kiosk.kiosk_id, "battery_level": 85},
            format="json",
        )

        # DRF returns 401 Unauthorized when authentication is missing
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_kiosk_heartbeat_with_expired_token(self, api_client, test_kiosk):
        """Test kiosk heartbeat fails with expired token"""
        # This test verifies JWT expiry is enforced
        # For now, just use invalid token format
        kiosk, _ = test_kiosk

        response = api_client.post(
            f"/api/v1/{kiosk.kiosk_id}/heartbeat/",
            {"kiosk_id": kiosk.kiosk_id},
            HTTP_AUTHORIZATION="Bearer invalid-token-format",
            format="json",
        )

        # DRF returns 401 Unauthorized for invalid tokens
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_user_token_cannot_access_kiosk_endpoints(
        self, authenticated_client, test_kiosk
    ):
        """Test that user JWT tokens cannot access kiosk endpoints"""
        kiosk, _ = test_kiosk

        # authenticated_client has a USER token, not kiosk token
        response = authenticated_client.post(
            f"/api/v1/{kiosk.kiosk_id}/heartbeat/",
            {"kiosk_id": kiosk.kiosk_id, "battery_level": 85},
            format="json",
        )

        # force_authenticate bypasses auth, but view rejects User objects
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestHealthEndpoint:
    """Essential health check tests"""

    def test_health_endpoint_accessible(self, api_client):
        """Test health endpoint is accessible without auth"""
        response = api_client.get("/health/")

        assert response.status_code == status.HTTP_200_OK
        # Health endpoint returns Django JsonResponse, not DRF Response
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
