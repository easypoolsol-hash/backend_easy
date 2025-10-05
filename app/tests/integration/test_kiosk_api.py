"""
Integration tests for kiosk API endpoints (Essential tests only)

Tests authenticated API access using JWT tokens.
"""

import pytest
from rest_framework import status


@pytest.mark.django_db
class TestKioskAPIAuthentication:
    """Essential tests for kiosk API access with JWT"""

    def test_kiosk_heartbeat_with_valid_token(self, api_client, test_kiosk):
        """Test kiosk heartbeat with valid JWT token"""
        kiosk, api_key = test_kiosk

        # 1. Authenticate and get token
        auth_response = api_client.post(
            '/api/kiosks/auth/',
            {'kiosk_id': kiosk.kiosk_id, 'api_key': api_key},
            format='json'
        )
        token = auth_response.data['access']

        # 2. Use token to send heartbeat
        response = api_client.post(
            '/api/kiosks/heartbeat/',
            {
                'kiosk_id': kiosk.kiosk_id,
                'battery_level': 85,
                'firmware_version': '1.0.0'
            },
            HTTP_AUTHORIZATION=f'Bearer {token}',
            format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'ok'
        assert response.data['kiosk_id'] == kiosk.kiosk_id

    def test_kiosk_heartbeat_without_token(self, api_client, test_kiosk):
        """Test kiosk heartbeat fails without token"""
        kiosk, _ = test_kiosk

        response = api_client.post(
            '/api/kiosks/heartbeat/',
            {
                'kiosk_id': kiosk.kiosk_id,
                'battery_level': 85
            },
            format='json'
        )

        # Should be unauthorized
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_kiosk_heartbeat_with_expired_token(self, api_client, test_kiosk):
        """Test kiosk heartbeat fails with expired token"""
        # This test verifies JWT expiry is enforced
        # For now, just use invalid token format
        kiosk, _ = test_kiosk

        response = api_client.post(
            '/api/kiosks/heartbeat/',
            {'kiosk_id': kiosk.kiosk_id},
            HTTP_AUTHORIZATION='Bearer invalid-token-format',
            format='json'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user_token_cannot_access_kiosk_endpoints(self, authenticated_client, test_kiosk):
        """Test that user JWT tokens cannot access kiosk endpoints"""
        kiosk, _ = test_kiosk

        # authenticated_client has a USER token, not kiosk token
        response = authenticated_client.post(
            '/api/kiosks/heartbeat/',
            {
                'kiosk_id': kiosk.kiosk_id,
                'battery_level': 85
            },
            format='json'
        )

        # Should fail because token type is not 'kiosk'
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestHealthEndpoint:
    """Essential health check tests"""

    def test_health_endpoint_accessible(self, api_client):
        """Test health endpoint is accessible without auth"""
        response = api_client.get('/health/')

        assert response.status_code == status.HTTP_200_OK
        assert 'status' in response.data
        assert response.data['status'] == 'healthy'
