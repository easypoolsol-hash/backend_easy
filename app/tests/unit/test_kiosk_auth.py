"""
Unit tests for kiosk authentication (Essential tests only)

Tests the core authentication logic without external dependencies.
"""

import hashlib

import pytest
from rest_framework import status


@pytest.mark.django_db
class TestKioskAuthentication:
    """Essential kiosk authentication tests"""

    def test_kiosk_auth_success(self, api_client, test_kiosk):
        """Test successful kiosk authentication"""
        kiosk, api_key = test_kiosk

        response = api_client.post(
            '/api/kiosks/auth/',
            {
                'kiosk_id': kiosk.kiosk_id,
                'api_key': api_key
            },
            format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data
        assert response.data['kiosk_id'] == kiosk.kiosk_id
        assert response.data['bus_id'] == str(kiosk.bus.bus_id)
        assert response.data['expires_in'] == 86400

    def test_kiosk_auth_invalid_api_key(self, api_client, test_kiosk):
        """Test authentication with wrong API key"""
        kiosk, _ = test_kiosk

        response = api_client.post(
            '/api/kiosks/auth/',
            {
                'kiosk_id': kiosk.kiosk_id,
                'api_key': 'wrong-api-key'
            },
            format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'detail' in response.data
        assert 'Invalid kiosk credentials' in str(response.data)

    def test_kiosk_auth_nonexistent_kiosk(self, api_client):
        """Test authentication with non-existent kiosk ID"""
        response = api_client.post(
            '/api/kiosks/auth/',
            {
                'kiosk_id': 'NONEXISTENT-KIOSK',
                'api_key': 'any-key'
            },
            format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Invalid kiosk credentials' in str(response.data)

    def test_kiosk_auth_inactive_kiosk(self, api_client, test_kiosk):
        """Test authentication with inactive kiosk"""
        kiosk, api_key = test_kiosk
        kiosk.is_active = False
        kiosk.save()

        response = api_client.post(
            '/api/kiosks/auth/',
            {
                'kiosk_id': kiosk.kiosk_id,
                'api_key': api_key
            },
            format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'inactive' in str(response.data).lower()

    def test_kiosk_auth_missing_credentials(self, api_client):
        """Test authentication with missing fields"""
        # Missing api_key
        response = api_client.post(
            '/api/kiosks/auth/',
            {'kiosk_id': 'TEST-KIOSK-001'},
            format='json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Missing kiosk_id
        response = api_client.post(
            '/api/kiosks/auth/',
            {'api_key': 'test-key'},
            format='json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_api_key_properly_hashed(self, test_kiosk):
        """Test that API key is stored as SHA-256 hash"""
        kiosk, api_key = test_kiosk

        # Verify hash matches
        expected_hash = hashlib.sha256(api_key.encode()).hexdigest()
        assert kiosk.api_key_hash == expected_hash

        # Verify plaintext is NOT stored
        assert api_key not in kiosk.api_key_hash

    def test_jwt_token_contains_kiosk_metadata(self, api_client, test_kiosk):
        """Test JWT token contains correct kiosk information"""
        kiosk, api_key = test_kiosk

        response = api_client.post(
            '/api/kiosks/auth/',
            {
                'kiosk_id': kiosk.kiosk_id,
                'api_key': api_key
            },
            format='json'
        )

        # Decode JWT (don't validate signature, just check payload)
        import jwt
        token = response.data['access']
        payload = jwt.decode(token, options={"verify_signature": False})

        assert payload['kiosk_id'] == kiosk.kiosk_id
        assert payload['type'] == 'kiosk'
