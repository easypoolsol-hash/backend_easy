"""
End-to-end tests for complete kiosk workflow (Essential tests only)

Tests the full flow: Auth → Heartbeat → Log
"""

import pytest
from rest_framework import status


@pytest.mark.django_db
class TestKioskWorkflow:
    """Essential end-to-end kiosk workflow test"""

    def test_complete_kiosk_workflow(self, api_client, test_kiosk):
        """
        Test complete kiosk workflow:
        1. Authenticate with kiosk_id + api_key
        2. Get JWT token
        3. Send heartbeat
        4. Send log
        """
        kiosk, api_key = test_kiosk

        # Step 1: Authenticate
        auth_response = api_client.post(
            '/api/kiosks/auth/',
            {
                'kiosk_id': kiosk.kiosk_id,
                'api_key': api_key
            },
            format='json'
        )

        assert auth_response.status_code == status.HTTP_200_OK
        assert 'access' in auth_response.data
        token = auth_response.data['access']

        # Step 2: Send heartbeat with token
        heartbeat_response = api_client.post(
            '/api/kiosks/heartbeat/',
            {
                'kiosk_id': kiosk.kiosk_id,
                'battery_level': 90,
                'firmware_version': '1.0.0',
                'storage_used_mb': 512
            },
            HTTP_AUTHORIZATION=f'Bearer {token}',
            format='json'
        )

        assert heartbeat_response.status_code == status.HTTP_200_OK
        assert heartbeat_response.data['status'] == 'ok'

        # Step 3: Send device log with token
        log_response = api_client.post(
            '/api/kiosks/log/',
            {
                'kiosk_id': kiosk.kiosk_id,
                'logs': [
                    {
                        'level': 'INFO',
                        'message': 'Kiosk started successfully',
                        'metadata': {'version': '1.0.0'}
                    }
                ]
            },
            HTTP_AUTHORIZATION=f'Bearer {token}',
            format='json'
        )

        assert log_response.status_code == status.HTTP_200_OK
        assert log_response.data['status'] == 'ok'
        assert log_response.data['logged_count'] == 1

        # Verify workflow completed successfully
        assert True  # All steps passed

    def test_workflow_fails_without_authentication(self, api_client, test_kiosk):
        """Test workflow fails if kiosk doesn't authenticate first"""
        kiosk, _ = test_kiosk

        # Try heartbeat without auth
        response = api_client.post(
            '/api/kiosks/heartbeat/',
            {
                'kiosk_id': kiosk.kiosk_id,
                'battery_level': 90
            },
            format='json'
        )

        # Should fail
        assert response.status_code == status.HTTP_403_FORBIDDEN
