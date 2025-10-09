"""
Unit tests for kiosk activation (Secure authentication only)

Tests the core activation logic without external dependencies.
"""

import json

import jwt
import pytest
from rest_framework import status


@pytest.mark.django_db
class TestKioskActivation:
    """Essential kiosk activation tests"""

    def test_kiosk_activation_success(self, api_client, test_kiosk, openapi_helper):
        """Test successful kiosk activation with valid token"""
        kiosk, activation_token = test_kiosk

        # Test the real activation endpoint
        response = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK

    def test_kiosk_activation_invalid_token(
        self, api_client, test_kiosk, openapi_helper
    ):
        """Test activation with wrong activation token"""
        kiosk, _ = test_kiosk

        response = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"kiosk_id": kiosk.kiosk_id, "activation_token": "invalid-token-123"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = json.loads(response.content.decode())
        assert "Invalid or already used activation token" in response_data["error"]

    def test_kiosk_activation_nonexistent_kiosk(self, api_client, openapi_helper):
        """Test activation with non-existent kiosk ID"""
        response = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"kiosk_id": "NONEXISTENT-KIOSK", "activation_token": "some-token"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = json.loads(response.content.decode())
        assert "Invalid kiosk_id" in response_data["error"]

    def test_kiosk_activation_missing_fields(self, api_client, openapi_helper):
        """Test activation with missing fields"""
        # Missing activation_token
        response = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"kiosk_id": "TEST-KIOSK-001"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Missing kiosk_id
        response = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"activation_token": "some-token"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_activation_token_one_time_use(
        self, api_client, test_kiosk, openapi_helper
    ):
        """Test that activation tokens can only be used once"""
        kiosk, activation_token = test_kiosk

        # First activation should succeed
        response1 = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        assert response1.status_code == status.HTTP_200_OK

        # Second activation with same token should fail
        response2 = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        assert response2.status_code == status.HTTP_400_BAD_REQUEST
        response_data = json.loads(response2.content.decode())
        assert "Invalid or already used activation token" in response_data["error"]

    def test_jwt_token_contains_kiosk_metadata(
        self, api_client, test_kiosk, openapi_helper
    ):
        """Test JWT token contains correct kiosk information"""
        kiosk, activation_token = test_kiosk

        response = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )

        response_data = json.loads(response.content.decode())
        token = response_data["access"]
        payload = jwt.decode(token, options={"verify_signature": False})

        assert payload["kiosk_id"] == kiosk.kiosk_id
        assert payload["type"] == "kiosk"
