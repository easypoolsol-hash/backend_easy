"""
Integration tests for kiosk sync endpoints - Critical API contract
Fortune 500 standard: Test critical user flows
"""

import pytest
from django.utils import timezone
from rest_framework import status

from app.tests.factories import BusFactory, FaceEmbeddingFactory, KioskFactory, StudentFactory


@pytest.mark.django_db
class TestSyncEndpoints:
    """Test sync API endpoints work correctly"""

    def test_check_updates_returns_correct_status(self, api_client):
        """CRITICAL: Check-updates must correctly detect when sync needed"""
        # Setup
        bus = BusFactory()
        kiosk = KioskFactory(bus=bus, api_key="test-key")
        student = StudentFactory()
        bus.students.add(student)

        # Update bus timestamp (simulate student change)
        bus.last_student_update = timezone.now()
        bus.save()

        # Authenticate kiosk
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {kiosk._api_key}')

        # Test needs update (old last_sync)
        old_sync = timezone.now() - timezone.timedelta(days=1)
        response = api_client.get(
            f'/api/v1/kiosk/{kiosk.kiosk_id}/check-updates/',
            {'last_sync': old_sync.isoformat()}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['needs_update'] is True
        assert 'current_version' in data
        assert 'student_count' in data
        assert 'embedding_count' in data
        assert 'content_hash' in data

    def test_check_updates_no_update_needed(self, api_client):
        """CRITICAL: Should return false when kiosk is up to date"""
        bus = BusFactory()
        kiosk = KioskFactory(bus=bus, api_key="test-key")

        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {kiosk._api_key}')

        # Test no update needed (recent last_sync)
        recent_sync = timezone.now()
        response = api_client.get(
            f'/api/v1/kiosk/{kiosk.kiosk_id}/check-updates/',
            {'last_sync': recent_sync.isoformat()}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['needs_update'] is False

    def test_download_snapshot_returns_valid_url(self, api_client):
        """CRITICAL: Snapshot download must return valid signed URL"""
        bus = BusFactory()
        kiosk = KioskFactory(bus=bus, api_key="test-key")
        student = StudentFactory()
        bus.students.add(student)
        FaceEmbeddingFactory(student=student)

        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {kiosk._api_key}')

        response = api_client.get(f'/api/v1/kiosk/{kiosk.kiosk_id}/snapshot/')

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert 'download_url' in data
        assert 'checksum' in data
        assert 'size_bytes' in data
        assert 'expires_at' in data
        assert data['size_bytes'] > 0
        assert len(data['checksum']) == 64  # SHA-256 hex

    def test_heartbeat_updates_kiosk_status(self, api_client):
        """CRITICAL: Heartbeat must update KioskStatus"""
        from app.kiosks.models import KioskStatus

        bus = BusFactory()
        kiosk = KioskFactory(bus=bus, api_key="test-key")

        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {kiosk._api_key}')

        heartbeat_data = {
            'timestamp': timezone.now().isoformat(),
            'database_version': '2025-10-06T14:30:00Z',
            'database_hash': 'a3f5d2b1c8e9f0a1',
            'student_count': 48,
            'embedding_count': 144,
            'health': {
                'battery_level': 85,
                'is_charging': True,
                'storage_available_mb': 5000,
                'camera_active': True,
                'network_type': 'wifi',
                'app_version': '1.0.0'
            }
        }

        response = api_client.post(
            f'/api/v1/kiosk/{kiosk.kiosk_id}/heartbeat/',
            heartbeat_data,
            format='json'
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify KioskStatus updated
        kiosk_status = KioskStatus.objects.get(kiosk=kiosk)
        assert kiosk_status.database_version == '2025-10-06T14:30:00Z'
        assert kiosk_status.student_count == 48
        assert kiosk_status.embedding_count == 144
        assert kiosk_status.battery_level == 85
        assert kiosk_status.is_charging is True
        assert kiosk_status.status in ['ok', 'warning', 'critical']

    def test_heartbeat_sets_critical_on_low_battery(self, api_client):
        """CRITICAL: Low battery must trigger critical status"""
        from app.kiosks.models import KioskStatus

        bus = BusFactory()
        kiosk = KioskFactory(bus=bus, api_key="test-key")

        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {kiosk._api_key}')

        heartbeat_data = {
            'timestamp': timezone.now().isoformat(),
            'database_version': '2025-10-06T14:30:00Z',
            'database_hash': 'abc123',
            'student_count': 48,
            'embedding_count': 144,
            'health': {
                'battery_level': 5,  # Critical low
                'is_charging': False,
                'storage_available_mb': 5000
            }
        }

        response = api_client.post(
            f'/api/v1/kiosk/{kiosk.kiosk_id}/heartbeat/',
            heartbeat_data,
            format='json'
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        kiosk_status = KioskStatus.objects.get(kiosk=kiosk)
        assert kiosk_status.status == 'critical'

    def test_unauthorized_access_rejected(self, api_client):
        """CRITICAL: Must reject requests without valid token"""
        kiosk = KioskFactory(api_key="test-key")

        # No auth header
        response = api_client.get(f'/api/v1/kiosk/{kiosk.kiosk_id}/check-updates/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # Wrong token
        api_client.credentials(HTTP_AUTHORIZATION='Bearer wrong-token')
        response = api_client.get(f'/api/v1/kiosk/{kiosk.kiosk_id}/check-updates/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
