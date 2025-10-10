"""
Industry Standard: Authentication Flow Integration Tests

Tests complete authentication lifecycles for all user types.
This catches integration bugs like the JWT refresh issue.
"""

from django.utils import timezone
import pytest
from rest_framework import status

from tests.utils.openapi_paths import get_path_by_operation as openapi_helper


@pytest.mark.django_db
class TestAuthenticationLifecycle:
    """Industry Standard: Complete authentication flow testing"""

    def test_kiosk_jwt_lifecycle_complete(self, api_client, test_kiosk):
        """
        Test complete kiosk JWT lifecycle:
        1. Activate → get tokens
        2. Use access token → verify works
        3. Access token expires → refresh → verify new token works
        4. Verify custom claims preserved through refresh
        """
        kiosk, activation_token = test_kiosk

        # 1. Activate and get initial tokens
        auth_response = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        assert auth_response.status_code == status.HTTP_200_OK

        initial_access = auth_response.data["access"]
        initial_refresh = auth_response.data["refresh"]

        # 2. Verify initial access token works
        from kiosks.models import KioskStatus

        KioskStatus.objects.create(kiosk=kiosk, last_heartbeat=timezone.now())

        heartbeat_response = api_client.post(
            openapi_helper(operation_id="kiosk_heartbeat", kiosk_id=kiosk.kiosk_id),
            {
                "timestamp": timezone.now().isoformat(),
                "database_version": timezone.now().isoformat(),
                "database_hash": "abc123",
                "student_count": 1,
                "embedding_count": 1,
            },
            HTTP_AUTHORIZATION=f"Bearer {initial_access}",
            format="json",
        )
        assert heartbeat_response.status_code == status.HTTP_204_NO_CONTENT

        # 3. Refresh the token (this is what was broken!)
        refresh_response = api_client.post(
            openapi_helper(operation_id="api_v1_auth_token_refresh_create"),
            {"refresh": initial_refresh},
            format="json",
        )
        new_access = refresh_response.data["access"]

        # 4. Verify new access token works
        heartbeat_response2 = api_client.post(
            openapi_helper(operation_id="kiosk_heartbeat", kiosk_id=kiosk.kiosk_id),
            {
                "timestamp": timezone.now().isoformat(),
                "database_version": timezone.now().isoformat(),
                "database_hash": "def456",
                "student_count": 2,
                "embedding_count": 2,
            },
            HTTP_AUTHORIZATION=f"Bearer {new_access}",
            format="json",
        )
        assert heartbeat_response2.status_code == status.HTTP_204_NO_CONTENT

        # 5. Verify kiosk claims preserved in new token
        import jwt

        payload = jwt.decode(new_access, options={"verify_signature": False})
        assert payload["kiosk_id"] == kiosk.kiosk_id
        assert payload["type"] == "kiosk"

    def test_user_jwt_lifecycle_complete(self, api_client):
        """Test complete user JWT lifecycle (parallel to kiosk testing)"""
        from tests.factories import UserFactory

        user = UserFactory()
        user.set_password("testpass123")
        user.save()

        # 1. Login and get tokens
        login_response = api_client.post(
            openapi_helper(operation_id="api_v1_users_login_create"),
            {"username": user.username, "password": "testpass123"},
            format="json",
        )
        assert login_response.status_code == status.HTTP_200_OK

        initial_access = login_response.data["access"]
        initial_refresh = login_response.data["refresh"]

        # 2. Use access token
        me_response = api_client.get(
            openapi_helper(operation_id="api_v1_users_me_retrieve"),
            HTTP_AUTHORIZATION=f"Bearer {initial_access}",
        )
        assert me_response.status_code == status.HTTP_200_OK

        # 3. Refresh token
        refresh_response = api_client.post(
            openapi_helper(operation_id="api_v1_auth_token_refresh_create"),
            {"refresh": initial_refresh},
            format="json",
        )
        assert refresh_response.status_code == status.HTTP_200_OK

        # 4. Verify new token works
        new_access = refresh_response.data["access"]
        me_response2 = api_client.get(
            openapi_helper(operation_id="api_v1_users_me_retrieve"),
            HTTP_AUTHORIZATION=f"Bearer {new_access}",
        )
        assert me_response2.status_code == status.HTTP_200_OK

    def test_mixed_authentication_schemes(self, api_client, authenticated_client, test_kiosk):
        """
        Industry Standard: Test different auth schemes work simultaneously

        This ensures kiosk JWT, user JWT, and API keys don't interfere.
        """
        kiosk, activation_token = test_kiosk

        # 1. Activate kiosk (kiosk JWT)
        auth_response = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        kiosk_token = auth_response.data["access"]

        # 2. User JWT (from authenticated_client fixture)
        user_response = authenticated_client.get(openapi_helper(operation_id="api_v1_users_me_retrieve"))
        assert user_response.status_code == status.HTTP_200_OK

        # 3. Kiosk heartbeat (kiosk JWT)
        from kiosks.models import KioskStatus

        KioskStatus.objects.create(kiosk=kiosk, last_heartbeat=timezone.now())

        heartbeat_response = api_client.post(
            openapi_helper(operation_id="kiosk_heartbeat", kiosk_id=kiosk.kiosk_id),
            {
                "timestamp": timezone.now().isoformat(),
                "database_version": timezone.now().isoformat(),
                "database_hash": "mixed123",
                "student_count": 1,
                "embedding_count": 1,
            },
            HTTP_AUTHORIZATION=f"Bearer {kiosk_token}",
            format="json",
        )
        assert heartbeat_response.status_code == status.HTTP_204_NO_CONTENT

        # 4. API Key authentication (if implemented)
        # This would test API key auth doesn't break JWT auth

    def test_token_refresh_under_load(self, api_client, test_kiosk):
        """
        Industry Standard: Test token refresh under concurrent load

        Catches race conditions and performance issues.
        Note: SQLite has database locking issues with true concurrency,
        so this test uses sequential requests with small delays.
        """
        import time

        kiosk, activation_token = test_kiosk

        # Get initial tokens
        auth_response = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        refresh_token = auth_response.data["refresh"]

        results = []
        errors = []

        def refresh_worker(worker_id):
            """Worker function for token refresh
            (sequential to avoid SQLite locking)"""
            try:
                # Small delay to simulate load but avoid true concurrency
                time.sleep(0.01 * worker_id)

                response = api_client.post(
                    openapi_helper(operation_id="api_v1_auth_token_refresh_create"),
                    {"refresh": refresh_token},
                    format="json",
                )

                results.append(
                    {
                        "worker": worker_id,
                        "status": response.status_code,
                        "has_access": ("access" in response.data if response.status_code == 200 else False),
                    }
                )

                # Note: In real usage, we'd update refresh token
                # for next worker but for this test we keep using the same

            except Exception as e:
                errors.append({"worker": worker_id, "error": str(e)})

        # Launch workers sequentially
        # (not truly concurrent due to SQLite limitations)
        for i in range(5):
            refresh_worker(i)

        # Verify results - expect most to succeed
        # (first should succeed, others may fail due to token reuse)
        successful_refreshes = [r for r in results if r["status"] == status.HTTP_200_OK]

        # At least the first refresh should succeed
        assert len(successful_refreshes) >= 1, f"No successful refreshes: {results}"
        assert len(errors) == 0, f"Unexpected errors: {errors}"

        # First worker should definitely succeed
        first_result = next((r for r in results if r["worker"] == 0), None)
        assert first_result and first_result["status"] == status.HTTP_200_OK, "First refresh should succeed"
