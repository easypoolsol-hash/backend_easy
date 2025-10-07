"""
Unit tests for kiosk activation (Secure authentication only)

Tests the core activation logic without external dependencies.
"""

import pytest
from django.test import Client, override_settings
from rest_framework import status


@pytest.mark.django_db
class TestKioskActivation:
    """Essential kiosk activation tests"""

    @override_settings(
        REST_FRAMEWORK={
            "DEFAULT_AUTHENTICATION_CLASSES": [],
            "DEFAULT_PERMISSION_CLASSES": [],
            "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
            "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
            "TEST_REQUEST_DEFAULT_FORMAT": "json",
        }
    )
    def test_kiosk_activation_success(self, test_kiosk):
        """Test successful kiosk activation with valid token"""
        from django.conf import settings

        print("RUNTIME REST_FRAMEWORK in test:", settings.REST_FRAMEWORK)

        client = Client(enforce_csrf_checks=False)  # Explicitly disable CSRF

        kiosk, activation_token = test_kiosk

        # Test the real activation endpoint
        response = client.post(
            "/api/v1/kiosks/activate/",
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            content_type="application/json",
        )

        print("Response status:", response.status_code)
        print("Response content:", response.content.decode())

        assert response.status_code == 200

    def test_kiosk_activation_invalid_token(self, api_client, test_kiosk):
        """Test activation with wrong activation token"""
        kiosk, _ = test_kiosk

        response = api_client.post(
            "/api/v1/kiosks/activate/",
            {"kiosk_id": kiosk.kiosk_id, "activation_token": "invalid-token-123"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        import json

        response_data = json.loads(response.content.decode())
        assert "Invalid or already used activation token" in response_data["error"]

    def test_kiosk_activation_nonexistent_kiosk(self, api_client):
        """Test activation with non-existent kiosk ID"""
        response = api_client.post(
            "/api/v1/kiosks/activate/",
            {"kiosk_id": "NONEXISTENT-KIOSK", "activation_token": "some-token"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        import json

        response_data = json.loads(response.content.decode())
        assert "Invalid kiosk_id" in response_data["error"]

    def test_kiosk_activation_missing_fields(self, api_client):
        """Test activation with missing fields"""
        # Missing activation_token
        response = api_client.post(
            "/api/v1/kiosks/activate/", {"kiosk_id": "TEST-KIOSK-001"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Missing kiosk_id
        response = api_client.post(
            "/api/v1/kiosks/activate/", {"activation_token": "some-token"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_activation_token_one_time_use(self, api_client, test_kiosk):
        """Test that activation tokens can only be used once"""
        kiosk, activation_token = test_kiosk

        # First activation should succeed
        response1 = api_client.post(
            "/api/v1/kiosks/activate/",
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        assert response1.status_code == status.HTTP_200_OK

        # Second activation with same token should fail
        response2 = api_client.post(
            "/api/v1/kiosks/activate/",
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        assert response2.status_code == status.HTTP_400_BAD_REQUEST
        import json

        response_data = json.loads(response2.content.decode())
        assert "Invalid or already used activation token" in response_data["error"]

    def test_jwt_token_contains_kiosk_metadata(self, api_client, test_kiosk):
        """Test JWT token contains correct kiosk information"""
        kiosk, activation_token = test_kiosk

        response = api_client.post(
            "/api/v1/kiosks/activate/",
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )

        # Decode JWT (don't validate signature, just check payload)
        import json

        import jwt

        response_data = json.loads(response.content.decode())
        token = response_data["access"]
        payload = jwt.decode(token, options={"verify_signature": False})

        assert payload["kiosk_id"] == kiosk.kiosk_id
        assert payload["type"] == "kiosk"
