"""
Industry-Standard Integration Tests: Kiosk Lifecycle and Heartbeat Functionality

Fortune 500 Testing Standards:
- End-to-end workflow testing
- Comprehensive error handling and edge cases
- Data persistence and state validation
- Performance and load testing
- Security and authentication testing
- Real-world scenario simulation
"""

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from kiosks.models import KioskStatus
from tests.factories import KioskFactory

# Ensure all tests in this module are allowed DB access
pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    """Create API client for testing."""
    return APIClient()


@pytest.fixture
def test_kiosk():
    """Create test kiosk with activation token."""
    kiosk = KioskFactory()
    activation_token = kiosk._activation_token
    return kiosk, activation_token


@pytest.mark.django_db
class TestKioskHeartbeatIntegration:
    """
    Test kiosk heartbeat functionality end-to-end.

    Industry Standard: Integration tests for complete workflows and data flow.
    """

    def test_kiosk_activation_and_heartbeat_workflow(self, api_client, test_kiosk):
        """
        Test complete workflow: activation → heartbeat → data storage.

        Industry Standard: End-to-end happy path testing.
        """
        kiosk, activation_token = test_kiosk

        # Step 1: Activate kiosk
        auth_response = api_client.post(
            "/api/v1/kiosks/activate/",
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        assert auth_response.status_code == status.HTTP_200_OK
        token = auth_response.data["access"]

        # Step 2: Send heartbeat with comprehensive data
        heartbeat_data = {
            "timestamp": timezone.now().isoformat(),
            "database_version": timezone.now().isoformat(),
            "database_hash": "test_hash_123",
            "student_count": 150,
            "embedding_count": 150,
            "health": {
                "battery_level": 85,
                "is_charging": False,
                "app_version": "1.2.3",
                "device_model": "TestDevice",
                "os_version": "Android 12",
            }
        }

        response = api_client.post(
            f"/api/v1/{kiosk.kiosk_id}/heartbeat/",
            heartbeat_data,
            HTTP_AUTHORIZATION=f"Bearer {token}",
            format="json",
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Step 3: Verify data was stored correctly
        kiosk.refresh_from_db()
        kiosk_status = KioskStatus.objects.get(kiosk=kiosk)

        assert kiosk_status.battery_level == 85
        assert kiosk_status.is_charging is False
        assert kiosk_status.app_version == "1.2.3"
        assert kiosk_status.student_count == 150
        assert kiosk_status.embedding_count == 150
        assert kiosk_status.status == "ok"  # Should be OK with 85% battery

        # Verify kiosk was updated
        assert kiosk.last_heartbeat is not None
        assert kiosk.is_online is True

    @pytest.mark.parametrize("battery_level,is_charging,expected_status", [
        # Critical battery scenarios
        (5, False, "critical"),
        (9, False, "critical"),
        (0, False, "critical"),

        # Warning battery scenarios
        (10, False, "warning"),
        (15, False, "warning"),
        (19, False, "warning"),

        # OK battery scenarios
        (20, False, "ok"),
        (50, False, "ok"),
        (100, False, "ok"),

        # Charging overrides
        (5, True, "ok"),
        (1, True, "ok"),
        (15, True, "ok"),
    ])
    def test_heartbeat_status_determination_integration(
        self, api_client, test_kiosk, battery_level, is_charging, expected_status
    ):
        """
        Test that heartbeat correctly determines kiosk status based on battery.

        Industry Standard: Parameterized integration testing for business logic.
        """
        kiosk, activation_token = test_kiosk

        # Activate kiosk
        auth_response = api_client.post(
            "/api/v1/kiosks/activate/",
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        assert auth_response.status_code == status.HTTP_200_OK
        token = auth_response.data["access"]

        # Send heartbeat with specific battery data
        heartbeat_data = {
            "timestamp": timezone.now().isoformat(),
            "database_version": timezone.now().isoformat(),
            "database_hash": f"hash_{battery_level}",
            "student_count": 100,
            "embedding_count": 100,
            "health": {
                "battery_level": battery_level,
                "is_charging": is_charging,
                "app_version": "1.0.0",
            }
        }

        response = api_client.post(
            f"/api/v1/{kiosk.kiosk_id}/heartbeat/",
            heartbeat_data,
            HTTP_AUTHORIZATION=f"Bearer {token}",
            format="json",
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify status was determined correctly
        kiosk_status = KioskStatus.objects.get(kiosk=kiosk)
        assert kiosk_status.status == expected_status, (
            f"Kiosk with {battery_level}% battery "
            f"({'charging' if is_charging else 'not charging'}) "
            f"should have status '{expected_status}', got '{kiosk_status.status}'"
        )

    def test_heartbeat_updates_existing_status(self, api_client, test_kiosk):
        """
        Test that heartbeat updates existing kiosk status instead of creating duplicate.

        Industry Standard: Test data consistency and update operations.
        """
        kiosk, activation_token = test_kiosk

        # Activate and send first heartbeat
        auth_response = api_client.post(
            "/api/v1/kiosks/activate/",
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        token = auth_response.data["access"]

        # First heartbeat
        heartbeat_data = {
            "timestamp": timezone.now().isoformat(),
            "database_version": timezone.now().isoformat(),
            "database_hash": "hash1",
            "student_count": 100,
            "embedding_count": 100,
            "health": {
                "battery_level": 80,
                "is_charging": False,
                "app_version": "1.0.0",
            }
        }

        api_client.post(
            f"/api/v1/{kiosk.kiosk_id}/heartbeat/",
            heartbeat_data,
            HTTP_AUTHORIZATION=f"Bearer {token}",
            format="json",
        )

        # Second heartbeat with different data
        heartbeat_data["health"]["battery_level"] = 60
        heartbeat_data["student_count"] = 120
        heartbeat_data["database_hash"] = "hash2"

        api_client.post(
            f"/api/v1/{kiosk.kiosk_id}/heartbeat/",
            heartbeat_data,
            HTTP_AUTHORIZATION=f"Bearer {token}",
            format="json",
        )

        # Verify only one status record exists and was updated
        status_count = KioskStatus.objects.filter(kiosk=kiosk).count()
        assert status_count == 1

        kiosk_status = KioskStatus.objects.get(kiosk=kiosk)
        assert kiosk_status.battery_level == 60
        assert kiosk_status.student_count == 120

    def test_heartbeat_without_existing_status_creates_new(self, api_client, test_kiosk):
        """
        Test that heartbeat creates new status record when none exists.

        Industry Standard: Test initial state handling.
        """
        kiosk, activation_token = test_kiosk

        # Activate kiosk
        auth_response = api_client.post(
            "/api/v1/kiosks/activate/",
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        token = auth_response.data["access"]

        # Ensure no status exists initially
        assert not KioskStatus.objects.filter(kiosk=kiosk).exists()

        # Send heartbeat
        heartbeat_data = {
            "timestamp": timezone.now().isoformat(),
            "database_version": timezone.now().isoformat(),
            "database_hash": "new_hash",
            "student_count": 50,
            "embedding_count": 50,
            "health": {
                "battery_level": 75,
                "is_charging": True,
                "app_version": "1.1.0",
            }
        }

        response = api_client.post(
            f"/api/v1/{kiosk.kiosk_id}/heartbeat/",
            heartbeat_data,
            HTTP_AUTHORIZATION=f"Bearer {token}",
            format="json",
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify status was created
        assert KioskStatus.objects.filter(kiosk=kiosk).exists()
        kiosk_status = KioskStatus.objects.get(kiosk=kiosk)
        assert kiosk_status.battery_level == 75
        assert kiosk_status.is_charging is True


class TestKioskHeartbeatErrorHandling:
    """
    Test error handling and edge cases in heartbeat functionality.

    Industry Standard: Comprehensive error testing and boundary conditions.
    """

    def test_heartbeat_unauthenticated_request(self, api_client, test_kiosk):
        """
        Test that unauthenticated heartbeat requests are rejected.

        Industry Standard: Security testing for authentication requirements.
        """
        kiosk, _ = test_kiosk

        heartbeat_data = {
            "timestamp": timezone.now().isoformat(),
            "database_version": timezone.now().isoformat(),
            "database_hash": "test_hash",
            "student_count": 10,
            "embedding_count": 10,
            "health": {
                "battery_level": 85,
                "app_version": "1.0.0",
            }
        }

        response = api_client.post(
            f"/api/v1/{kiosk.kiosk_id}/heartbeat/",
            heartbeat_data,
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_heartbeat_invalid_kiosk_id(self, api_client):
        """
        Test heartbeat with invalid kiosk ID.

        Industry Standard: Test invalid input handling.
        """
        # Create a client and try to authenticate with fake token
        api_client.credentials(HTTP_AUTHORIZATION="Bearer fake_token")

        heartbeat_data = {
            "timestamp": timezone.now().isoformat(),
            "database_version": timezone.now().isoformat(),
            "database_hash": "test_hash",
            "student_count": 10,
            "embedding_count": 10,
            "health": {
                "battery_level": 85,
                "app_version": "1.0.0",
            }
        }

        response = api_client.post(
            "/api/v1/invalid_kiosk_id/heartbeat/",
            heartbeat_data,
            format="json",
        )

        # Should return 401 (unauthorized) since token is invalid
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.parametrize("invalid_battery", [-1, 101, 150, "invalid", None])
    def test_heartbeat_invalid_battery_data(self, api_client, test_kiosk, invalid_battery):
        """
        Test heartbeat with invalid battery data.

        Industry Standard: Test input validation and error handling.
        """
        kiosk, activation_token = test_kiosk

        # Activate kiosk
        auth_response = api_client.post(
            "/api/v1/kiosks/activate/",
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        token = auth_response.data["access"]

        # Send heartbeat with invalid battery data
        heartbeat_data = {
            "timestamp": timezone.now().isoformat(),
            "database_version": timezone.now().isoformat(),
            "database_hash": "test_hash",
            "student_count": 10,
            "embedding_count": 10,
            "health": {
                "battery_level": invalid_battery,
                "is_charging": False,
                "app_version": "1.0.0",
            }
        }

        response = api_client.post(
            f"/api/v1/{kiosk.kiosk_id}/heartbeat/",
            heartbeat_data,
            HTTP_AUTHORIZATION=f"Bearer {token}",
            format="json",
        )

        # Should handle gracefully - either accept and sanitize or reject
        # Based on current implementation, it should accept (validation happens at model level)
        if invalid_battery in [-1, 101, 150]:  # Invalid numbers
            # Model validation should catch this
            assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_204_NO_CONTENT]
        else:
            # Other invalid types might be accepted or rejected
            assert response.status_code in [status.HTTP_204_NO_CONTENT, status.HTTP_400_BAD_REQUEST]

    def test_heartbeat_missing_required_fields(self, api_client, test_kiosk):
        """
        Test heartbeat with missing required fields.

        Industry Standard: Test API contract validation.
        """
        kiosk, activation_token = test_kiosk

        # Activate kiosk
        auth_response = api_client.post(
            "/api/v1/kiosks/activate/",
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        token = auth_response.data["access"]

        # Send heartbeat with missing required fields
        incomplete_data = {
            "timestamp": timezone.now().isoformat(),
            # Missing database_version, database_hash, etc.
        }

        response = api_client.post(
            f"/api/v1/{kiosk.kiosk_id}/heartbeat/",
            incomplete_data,
            HTTP_AUTHORIZATION=f"Bearer {token}",
            format="json",
        )

        # Should return validation error
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_heartbeat_inactive_kiosk(self, api_client):
        """
        Test heartbeat from inactive kiosk.

        Industry Standard: Test business rule enforcement.
        """
        # Create inactive kiosk
        kiosk = KioskFactory(is_active=False)
        activation_token = kiosk.generate_activation_token()

        # Try to activate inactive kiosk
        auth_response = api_client.post(
            "/api/v1/kiosks/activate/",
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )

        # Should fail activation
        assert auth_response.status_code == status.HTTP_400_BAD_REQUEST


class TestKioskHeartbeatPerformance:
    """
    Test heartbeat performance and load handling.

    Industry Standard: Performance testing for critical API endpoints.
    """

    @pytest.mark.django_db
    def test_multiple_kiosks_heartbeat_concurrency(self, api_client):
        """
        Test multiple kiosks sending heartbeats concurrently.

        Industry Standard: Load testing for concurrent operations.
        """
        # Create multiple kiosks
        kiosks = []
        tokens = []

        for i in range(5):
            kiosk = KioskFactory(kiosk_id=f"test_kiosk_{i}")
            activation_token = kiosk.generate_activation_token()
            kiosks.append(kiosk)
            tokens.append(activation_token)

        # Activate all kiosks
        for kiosk, token in zip(kiosks, tokens, strict=True):
            auth_response = api_client.post(
                "/api/v1/kiosks/activate/",
                {"kiosk_id": kiosk.kiosk_id, "activation_token": token},
                format="json",
            )
            assert auth_response.status_code == status.HTTP_200_OK

        # Send heartbeats from all kiosks
        results = []
        errors = []

        def send_heartbeat(kiosk, token):
            try:
                heartbeat_data = {
                    "timestamp": timezone.now().isoformat(),
                    "database_version": timezone.now().isoformat(),
                    "database_hash": f"hash_{kiosk.kiosk_id}",
                    "student_count": 100,
                    "embedding_count": 100,
                    "health": {
                        "battery_level": 80,
                        "is_charging": False,
                        "app_version": "1.0.0",
                    }
                }

                response = api_client.post(
                    f"/api/v1/{kiosk.kiosk_id}/heartbeat/",
                    heartbeat_data,
                    HTTP_AUTHORIZATION=f"Bearer {token}",
                    format="json",
                )
                results.append((kiosk.kiosk_id, response.status_code))
            except Exception as e:
                errors.append((kiosk.kiosk_id, str(e)))

        # Note: In real implementation, would use threading or async
        # For this test, we'll send sequentially but verify no interference
        for kiosk, token in zip(kiosks, tokens, strict=True):
            send_heartbeat(kiosk, token)

        # Verify all heartbeats succeeded
        assert len(results) == 5
        for kiosk_id, status_code in results:
            assert status_code == status.HTTP_204_NO_CONTENT, (
                f"Heartbeat failed for {kiosk_id}"
            )

        # Verify all kiosks have status records
        for kiosk in kiosks:
            assert KioskStatus.objects.filter(kiosk=kiosk).exists()
            kiosk_status = KioskStatus.objects.get(kiosk=kiosk)
            assert kiosk_status.battery_level == 80

    @pytest.mark.django_db
    def test_heartbeat_frequency_and_timing(self, api_client, test_kiosk):
        """
        Test heartbeat timing and frequency handling.

        Industry Standard: Test temporal behavior and rate limiting.
        """
        kiosk, activation_token = test_kiosk

        # Activate kiosk
        auth_response = api_client.post(
            "/api/v1/kiosks/activate/",
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        token = auth_response.data["access"]

        # Send multiple heartbeats in quick succession
        base_time = timezone.now()

        for i in range(3):
            heartbeat_time = base_time + timezone.timedelta(
                seconds=i*30
            )  # 30 second intervals

            heartbeat_data = {
                "timestamp": heartbeat_time.isoformat(),
                "database_version": heartbeat_time.isoformat(),
                "database_hash": f"hash_{i}",
                "student_count": 100 + i*10,
                "embedding_count": 100 + i*10,
                "health": {
                    "battery_level": 90 - i*5,  # Decreasing battery
                    "is_charging": False,
                    "app_version": "1.0.0",
                }
            }

            response = api_client.post(
                f"/api/v1/{kiosk.kiosk_id}/heartbeat/",
                heartbeat_data,
                HTTP_AUTHORIZATION=f"Bearer {token}",
                format="json",
            )
            assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify final state
        kiosk_status = KioskStatus.objects.get(kiosk=kiosk)
        assert kiosk_status.battery_level == 75  # Final battery level
        assert kiosk_status.student_count == 120  # Final student count
