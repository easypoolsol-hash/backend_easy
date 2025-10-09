"""
Industry Standard: Chaos Engineering Authentication Tests

Tests authentication behavior under failure conditions.
This catches issues that only appear during outages or performance problems.
"""

import gc
import os
from unittest.mock import patch

from django.core.cache import cache
from django.db import connection
from django.utils import timezone
import psutil
import pytest
from rest_framework import status


@pytest.mark.django_db
class TestAuthenticationChaosEngineering:
    """Industry Standard: Chaos engineering for authentication"""

    def test_auth_under_database_slowdown(self, api_client, test_kiosk):
        """
        Test authentication when database is slow.

        Catches issues where auth fails under DB load.
        """
        kiosk, activation_token = test_kiosk

        # Simulate slow database by patching database cursor
        original_execute = connection.cursor().execute

        def slow_execute(sql, params=None):
            """Simulate slow database query"""
            import time

            time.sleep(0.1)  # 100ms delay
            return original_execute(sql, params)

        with patch.object(connection.cursor(), "execute", side_effect=slow_execute):
            # This should still work even with slow DB
            response = api_client.post(
                "/api/v1/kiosks/activate/",
                {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
                format="json",
            )

            # Should succeed despite slow DB
            assert response.status_code == status.HTTP_200_OK
            assert "access" in response.data
            assert "refresh" in response.data

    def test_auth_under_redis_failure(self, api_client, test_kiosk):
        """
        Test authentication when Redis/cache is down.

        Catches issues where auth depends on cache but doesn't handle failures.
        """
        kiosk, activation_token = test_kiosk

        # Mock Redis/cache failure
        with patch.object(cache, "get", side_effect=Exception("Redis down")):
            with patch.object(cache, "set", side_effect=Exception("Redis down")):
                # Auth should still work without cache
                response = api_client.post(
                    "/api/v1/kiosks/activate/",
                    {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
                    format="json",
                )

                assert response.status_code == status.HTTP_200_OK

    def test_token_refresh_under_network_issues(self, api_client, test_kiosk):
        """
        Test token refresh when network/database has intermittent issues.

        Catches race conditions and partial failure handling.
        """
        kiosk, activation_token = test_kiosk

        # Get initial tokens
        auth_response = api_client.post(
            "/api/v1/kiosks/activate/",
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        refresh_token = auth_response.data["refresh"]

        # Simulate intermittent database failures
        call_count = 0
        original_execute = connection.cursor().execute

        def intermittent_failure(sql, params=None):
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:  # Every 3rd call fails
                raise Exception("Intermittent DB failure")
            return original_execute(sql, params)

        with patch.object(
            connection.cursor(), "execute", side_effect=intermittent_failure
        ):
            # Should eventually succeed with retry logic
            response = api_client.post(
                "/api/v1/auth/token/refresh/",
                {"refresh": refresh_token},
                format="json",
            )

            # Either succeeds or fails gracefully
            assert response.status_code in [
                status.HTTP_200_OK,  # Success
                status.HTTP_500_INTERNAL_SERVER_ERROR,  # Expected failure
            ]

    def test_auth_under_high_concurrency(self, api_client, test_kiosk):
        """
        Test authentication under high concurrent load.

        Catches race conditions and resource exhaustion.
        Note: SQLite has database locking issues with true concurrency,
        so this test uses sequential requests.
        """
        import time

        kiosk, activation_token = test_kiosk
        results = []
        errors = []

        def sequential_activation(worker_id):
            """Worker function for activation attempts
            (sequential to avoid SQLite locking)"""
            try:
                time.sleep(0.01 * worker_id)  # Stagger requests

                response = api_client.post(
                    "/api/v1/kiosks/activate/",
                    {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
                    format="json",
                )

                results.append(
                    {
                        "worker": worker_id,
                        "status": response.status_code,
                        "has_tokens": (
                            "access" in response.data
                            if response.status_code == 200
                            else False
                        ),
                    }
                )

            except Exception as e:
                errors.append({"worker": worker_id, "error": str(e)})

        # Launch workers sequentially
        # (not truly concurrent due to SQLite limitations)
        for i in range(10):
            sequential_activation(i)

        # At least one should succeed (the first one)
        success_count = sum(1 for r in results if r["status"] == status.HTTP_200_OK)

        # Should have exactly one successful activation
        # (first one succeeds, rest fail)
        assert success_count == 1, f"Expected 1 success, got {success_count}: {results}"

        # Check for reasonable error handling on failures
        failed_requests = [r for r in results if r["status"] not in [200, 400]]
        assert len(failed_requests) == 0, f"Unexpected errors: {failed_requests}"

    def test_auth_during_service_restart(self, api_client, test_kiosk):
        """
        Test authentication behavior during service restart scenarios.

        Catches issues with state management across restarts.
        Note: JWT tokens are stateless, so cache clearing
        doesn't invalidate them.
        """
        kiosk, activation_token = test_kiosk

        # Simulate service restart by clearing any in-memory state
        # This is a placeholder - in real chaos engineering you'd restart services

        # Test that auth still works after "restart"
        response = api_client.post(
            "/api/v1/kiosks/activate/",
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK

        # Test that tokens from before "restart" still work
        # (JWT tokens are stateless and don't depend on server cache)
        refresh_token = response.data["refresh"]

        # Simulate restart by clearing caches/session state
        cache.clear()

        # Refresh token should still work (JWT is stateless)
        refresh_response = api_client.post(
            "/api/v1/auth/token/refresh/",
            {"refresh": refresh_token},
            format="json",
        )

        # Should succeed because JWT tokens don't depend on cache
        assert refresh_response.status_code == status.HTTP_200_OK

    def test_auth_under_memory_pressure(self, api_client, test_kiosk):
        """
        Test authentication when system is under memory pressure.

        Catches memory leaks and inefficient auth processing.
        """

        kiosk, activation_token = test_kiosk

        # Get baseline memory
        process = psutil.Process(os.getpid())
        baseline_memory = process.memory_info().rss

        # Perform multiple auth operations
        for _i in range(50):  # Stress test
            response = api_client.post(
                "/api/v1/kiosks/activate/",
                {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
                format="json",
            )
            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_400_BAD_REQUEST,
            ]

        # Force garbage collection
        gc.collect()

        # Check memory usage didn't grow excessively
        final_memory = process.memory_info().rss
        memory_growth = final_memory - baseline_memory

        # Memory growth should be reasonable (< 50MB for 50 operations)
        assert (
            memory_growth < 50 * 1024 * 1024
        ), f"Excessive memory growth: {memory_growth / 1024 / 1024:.2f}MB"

    def test_auth_with_corrupted_database_state(self, api_client, test_kiosk):
        """
        Test authentication when database has corrupted/inconsistent state.

        Catches issues with data integrity and error handling.
        """
        kiosk, activation_token = test_kiosk

        # Simulate corrupted kiosk state (e.g., missing required fields)
        # Corrupt the activation token record by setting expires_at to past
        from kiosks.models import KioskActivationToken

        activation_token_obj = KioskActivationToken.objects.get(
            kiosk=kiosk, is_used=False
        )
        # Corrupt by setting expiration to past (token becomes invalid)
        activation_token_obj.expires_at = timezone.now() - timezone.timedelta(hours=1)
        activation_token_obj.save()

        # Auth should fail gracefully
        response = api_client.post(
            "/api/v1/kiosks/activate/",
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )

        # Should return a proper error, not crash
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

        # Should have error details
        assert "detail" in response.data or "error" in response.data
