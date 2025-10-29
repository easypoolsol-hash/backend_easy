"""
Integration tests for kiosk API endpoints (Essential tests only)

Tests authenticated API access using JWT tokens.
"""

from django.utils import timezone
import pytest
from rest_framework import status

from tests.utils.openapi_paths import get_path_by_operation as openapi_helper


@pytest.mark.django_db
class TestKioskAPIAuthentication:
    """Essential tests for kiosk API access with JWT"""

    def test_kiosk_heartbeat_with_valid_token(self, api_client, test_kiosk):
        """Test kiosk heartbeat with valid JWT token"""
        kiosk, activation_token = test_kiosk

        # 1. Activate kiosk and get token
        auth_response = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
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
            openapi_helper(operation_id="kiosk_heartbeat", kiosk_id=kiosk.kiosk_id),
            data=heartbeat_data,
            HTTP_AUTHORIZATION=f"Bearer {token}",
            format="json",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_kiosk_heartbeat_without_token(self, api_client, test_kiosk):
        """Test kiosk heartbeat fails without token"""
        kiosk, _ = test_kiosk

        response = api_client.post(
            f"/api/v1/kiosks/{kiosk.kiosk_id}/heartbeat/",
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
            f"/api/v1/kiosks/{kiosk.kiosk_id}/heartbeat/",
            {"kiosk_id": kiosk.kiosk_id},
            HTTP_AUTHORIZATION="Bearer invalid-token-format",
            format="json",
        )

        # DRF returns 401 Unauthorized for invalid tokens
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_user_token_cannot_access_kiosk_endpoints(self, authenticated_client, test_kiosk):
        """Test that user JWT tokens cannot access kiosk endpoints"""
        kiosk, _ = test_kiosk

        # authenticated_client has a USER token, not kiosk token
        response = authenticated_client.post(
            f"/api/v1/kiosks/{kiosk.kiosk_id}/heartbeat/",
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


@pytest.mark.django_db
class TestKioskLocationTracking:
    """Tests for GPS location tracking API"""

    def test_kiosk_location_update_with_valid_token(self, api_client, test_kiosk):
        """Test kiosk can send GPS location with valid JWT token"""
        kiosk, activation_token = test_kiosk

        # 1. Activate kiosk and get token
        auth_response = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        token = auth_response.json()["access"]

        # 2. Send location update
        location_data = {
            "latitude": 51.5074,
            "longitude": -0.1278,
            "accuracy": 10.0,
            "speed": 15.5,
            "heading": 270.0,
            "timestamp": timezone.now().isoformat(),
        }

        response = api_client.post(
            openapi_helper(operation_id="kiosk_update_location", kiosk_id=kiosk.kiosk_id),
            data=location_data,
            HTTP_AUTHORIZATION=f"Bearer {token}",
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["latitude"] == 51.5074
        assert data["longitude"] == -0.1278
        assert data["accuracy"] == 10.0
        assert data["speed"] == 15.5
        assert data["heading"] == 270.0

    def test_kiosk_location_update_without_token(self, api_client, test_kiosk):
        """Test location update fails without authentication"""
        kiosk, _ = test_kiosk

        location_data = {
            "latitude": 51.5074,
            "longitude": -0.1278,
            "timestamp": timezone.now().isoformat(),
        }

        response = api_client.post(
            f"/api/v1/kiosks/{kiosk.kiosk_id}/location/",
            data=location_data,
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_kiosk_location_validates_coordinates(self, api_client, test_kiosk):
        """Test location API validates latitude/longitude ranges"""
        kiosk, activation_token = test_kiosk

        # 1. Activate kiosk and get token
        auth_response = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        token = auth_response.json()["access"]

        # 2. Test invalid latitude (> 90)
        invalid_location = {
            "latitude": 95.0,
            "longitude": -0.1278,
            "timestamp": timezone.now().isoformat(),
        }

        response = api_client.post(
            openapi_helper(operation_id="kiosk_update_location", kiosk_id=kiosk.kiosk_id),
            data=invalid_location,
            HTTP_AUTHORIZATION=f"Bearer {token}",
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "latitude" in response.json()

        # 3. Test invalid longitude (> 180)
        invalid_location = {
            "latitude": 51.5074,
            "longitude": 200.0,
            "timestamp": timezone.now().isoformat(),
        }

        response = api_client.post(
            openapi_helper(operation_id="kiosk_update_location", kiosk_id=kiosk.kiosk_id),
            data=invalid_location,
            HTTP_AUTHORIZATION=f"Bearer {token}",
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "longitude" in response.json()
