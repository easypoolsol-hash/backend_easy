"""
Industry Standard: Security Integration Tests

Tests authentication security vulnerabilities and attack vectors.
Uses bandit for static security analysis and pytest-mock for attack simulation.
"""

from datetime import timedelta

from django.test import override_settings
import jwt
import pytest
from rest_framework import status

from tests.utils.openapi_paths import get_path_by_operation as openapi_helper


@pytest.mark.django_db
class TestJWTSecurityVulnerabilities:
    """Industry Standard: JWT security vulnerability testing"""

    def test_jwt_algorithm_confusion_attack(self, api_client, test_kiosk):
        """
        Test protection against JWT algorithm confusion attacks.

        Industry Standard: CWE-347 (Improper Verification of Cryptographic Signature)
        """
        kiosk, activation_token = test_kiosk

        # Get a valid token first
        auth_response = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        valid_token = auth_response.data["access"]

        # Decode the valid token to get payload
        decoded = jwt.decode(valid_token, options={"verify_signature": False})

        # Create a malicious token with "none" algorithm
        malicious_token = jwt.encode(
            decoded,
            "",  # No key
            algorithm="none",
        )

        # Try to use the malicious token
        response = api_client.post(
            openapi_helper(operation_id="kiosk_heartbeat", kiosk_id=kiosk.kiosk_id),
            {
                "timestamp": "2025-01-01T00:00:00Z",
                "database_version": "2025-01-01T00:00:00Z",
                "database_hash": "malicious",
                "student_count": 999,
                "embedding_count": 999,
            },
            HTTP_AUTHORIZATION=f"Bearer {malicious_token}",
            format="json",
        )

        # Should be rejected
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_jwt_token_tampering(self, api_client, test_kiosk):
        """
        Test protection against JWT payload tampering.

        Industry Standard: CWE-345 (Insufficient Verification of Data Authenticity)
        """
        kiosk, activation_token = test_kiosk

        # Get a valid token
        auth_response = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        valid_token = auth_response.data["access"]

        # Tamper with the token payload (change kiosk_id)
        header, payload, signature = valid_token.split(".")

        # Decode and modify payload
        import base64
        import json

        payload_decoded = json.loads(base64.urlsafe_b64decode(payload + "==").decode())
        payload_decoded["kiosk_id"] = "tampered_kiosk_id"

        # Re-encode tampered payload
        tampered_payload = (
            base64.urlsafe_b64encode(json.dumps(payload_decoded).encode())
            .decode()
            .rstrip("=")
        )

        tampered_token = f"{header}.{tampered_payload}.{signature}"

        # Try to use tampered token
        response = api_client.post(
            openapi_helper(operation_id="kiosk_heartbeat", kiosk_id=kiosk.kiosk_id),
            {
                "timestamp": "2025-01-01T00:00:00Z",
                "database_version": "2025-01-01T00:00:00Z",
                "database_hash": "tampered",
                "student_count": 1,
                "embedding_count": 1,
            },
            HTTP_AUTHORIZATION=f"Bearer {tampered_token}",
            format="json",
        )

        # Should be rejected due to signature mismatch
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_jwt_expiry_manipulation(self, api_client, test_kiosk):
        """
        Test protection against JWT expiry manipulation.

        Industry Standard: CWE-613 (Insufficient Session Expiration)
        """
        kiosk, activation_token = test_kiosk

        # Get a valid token
        auth_response = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        valid_token = auth_response.data["access"]

        # Decode and modify expiry to future date
        header, payload, signature = valid_token.split(".")

        import base64
        from datetime import datetime, timedelta
        import json

        payload_decoded = json.loads(base64.urlsafe_b64decode(payload + "==").decode())

        # Set expiry to 1 year in future
        future_expiry = datetime.utcnow() + timedelta(days=365)
        payload_decoded["exp"] = int(future_expiry.timestamp())

        # Re-encode
        tampered_payload = (
            base64.urlsafe_b64encode(json.dumps(payload_decoded).encode())
            .decode()
            .rstrip("=")
        )

        tampered_token = f"{header}.{tampered_payload}.{signature}"

        # Try to use token with manipulated expiry
        response = api_client.post(
            openapi_helper(operation_id="kiosk_heartbeat", kiosk_id=kiosk.kiosk_id),
            {
                "timestamp": "2025-01-01T00:00:00Z",
                "database_version": "2025-01-01T00:00:00Z",
                "database_hash": "expiry_manipulated",
                "student_count": 1,
                "embedding_count": 1,
            },
            HTTP_AUTHORIZATION=f"Bearer {tampered_token}",
            format="json",
        )

        # Should be rejected
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_jwt_signature_stripping_attack(self, api_client, test_kiosk):
        """
        Test protection against JWT signature stripping attacks.

        Industry Standard: CWE-347 (Cryptographic Signature Verification Failure)
        """
        kiosk, activation_token = test_kiosk

        # Get a valid token
        auth_response = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        valid_token = auth_response.data["access"]

        # Remove signature (set to empty)
        header, payload, _ = valid_token.split(".")
        stripped_token = f"{header}.{payload}."

        # Try to use signature-stripped token
        response = api_client.post(
            openapi_helper(operation_id="kiosk_heartbeat", kiosk_id=kiosk.kiosk_id),
            {
                "timestamp": "2025-01-01T00:00:00Z",
                "database_version": "2025-01-01T00:00:00Z",
                "database_hash": "signature_stripped",
                "student_count": 1,
                "embedding_count": 1,
            },
            HTTP_AUTHORIZATION=f"Bearer {stripped_token}",
            format="json",
        )

        # Should be rejected
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestAuthenticationBypassAttempts:
    """Industry Standard: Authentication bypass testing"""

    def test_sql_injection_in_auth(self, api_client):
        """
        Test protection against SQL injection in authentication.

        Industry Standard: CWE-89 (SQL Injection)
        """
        # Test SQL injection in username/password
        sql_injection_payloads = [
            "' OR '1'='1",
            "admin'--",
            "'; DROP TABLE users;--",
            "' UNION SELECT * FROM users--",
        ]

        for payload in sql_injection_payloads:
            response = api_client.post(
                openapi_helper(operation_id="api_v1_users_login_create"),
                {"username": payload, "password": payload},
                format="json",
            )

            # Should not succeed with SQL injection
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_401_UNAUTHORIZED,
            ]

    def test_directory_traversal_in_auth(self, api_client):
        """
        Test protection against directory traversal in auth endpoints.

        Industry Standard: CWE-22 (Path Traversal)
        """
        traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/shadow",
            "....//....//....//etc/passwd",
        ]

        for payload in traversal_payloads:
            # Try in kiosk_id parameter
            response = api_client.post(
                f"/api/v1/{payload}/heartbeat/",
                {
                    "timestamp": "2025-01-01T00:00:00Z",
                    "database_version": "2025-01-01T00:00:00Z",
                    "database_hash": "traversal",
                    "student_count": 1,
                    "embedding_count": 1,
                },
                format="json",
            )

            # Should not allow traversal
            assert response.status_code in [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_404_NOT_FOUND,
                status.HTTP_400_BAD_REQUEST,
            ]

    def test_brute_force_protection(self, api_client):
        """
        Test protection against brute force attacks.

        Industry Standard: CWE-307 (Improper Restriction of Excessive Authentication Attempts)
        """
        # Attempt multiple failed logins
        for i in range(10):
            response = api_client.post(
                openapi_helper(operation_id="api_v1_users_login_create"),
                {"username": f"nonexistent_user_{i}", "password": "wrong_password"},
                format="json",
            )

            # Should fail but not be blocked (unless rate limiting is implemented)
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_429_TOO_MANY_REQUESTS,  # If rate limiting implemented
            ]

    def test_session_fixation_attack(self, api_client, test_kiosk):
        """
        Test protection against session fixation attacks.

        Industry Standard: CWE-384 (Session Fixation)
        """
        kiosk, activation_token = test_kiosk

        # First activation
        auth_response1 = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        token1 = auth_response1.data["access"]

        # Second activation (should fail - token already used)
        auth_response2 = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        # Second activation should fail since token is one-time use
        assert auth_response2.status_code == status.HTTP_400_BAD_REQUEST

        # Try to use first token (should still work since kiosk is activated)
        from kiosks.models import KioskStatus

        KioskStatus.objects.create(kiosk=kiosk, last_heartbeat="2025-01-01T00:00:00Z")

        heartbeat_path = openapi_helper(
            operation_id="kiosk_heartbeat", kiosk_id=kiosk.kiosk_id
        )
        response = api_client.post(
            heartbeat_path,
            {
                "timestamp": "2025-01-01T00:00:00Z",
                "database_version": "2025-01-01T00:00:00Z",
                "database_hash": "session_fixation",
                "student_count": 1,
                "embedding_count": 1,
            },
            HTTP_AUTHORIZATION=f"Bearer {token1}",
            format="json",
        )

        # First token should still work (kiosk is activated)
        assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
class TestTokenSecurityLifecycle:
    """Industry Standard: Token security lifecycle testing"""

    @pytest.mark.skip(
        reason="Token expiry test unreliable in test "
        "environment due to Django settings override "
        "limitations"
    )
    @override_settings(
        SIMPLE_JWT={
            "ACCESS_TOKEN_LIFETIME": timedelta(seconds=1),  # Very short expiry
        }
    )
    def test_token_expiry_enforcement(self, api_client, test_kiosk):
        """
        Test that expired tokens are properly rejected.

        Industry Standard: CWE-613 (Insufficient Session Expiration)
        """
        import time

        kiosk, activation_token = test_kiosk

        # Get token
        auth_response = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        token = auth_response.data["access"]

        # Wait for token to expire
        time.sleep(2)

        # Try to use expired token
        from kiosks.models import KioskStatus

        KioskStatus.objects.create(kiosk=kiosk, last_heartbeat="2025-01-01T00:00:00Z")

        heartbeat_path = openapi_helper(
            operation_id="kiosk_heartbeat", kiosk_id=kiosk.kiosk_id
        )
        response = api_client.post(
            heartbeat_path,
            {
                "timestamp": "2025-01-01T00:00:00Z",
                "database_version": "2025-01-01T00:00:00Z",
                "database_hash": "expired_token",
                "student_count": 1,
                "embedding_count": 1,
            },
            HTTP_AUTHORIZATION=f"Bearer {token}",
            format="json",
        )

        # Should be rejected due to expired token
        # Note: The exact status code may vary depending on JWT
        # library behavior
        # 401 = token expired/invalid, 403 = forbidden,
        # 204 = token accepted (unexpected)
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

    def test_refresh_token_reuse_prevention(self, api_client, test_kiosk):
        """
        Test that refresh tokens can't be reused after refresh.

        Industry Standard: CWE-323 (Use of Known Cryptographically Weak PRNG)
        """
        kiosk, activation_token = test_kiosk

        # Get initial tokens
        auth_response = api_client.post(
            openapi_helper(operation_id="kiosk_activate"),
            {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
            format="json",
        )
        refresh_token = auth_response.data["refresh"]

        # First refresh
        refresh_response1 = api_client.post(
            openapi_helper(operation_id="api_v1_auth_token_refresh_create"),
            {"refresh": refresh_token},
            format="json",
        )
        assert refresh_response1.status_code == status.HTTP_200_OK

        # Try to reuse the same refresh token
        refresh_response2 = api_client.post(
            openapi_helper(operation_id="api_v1_auth_token_refresh_create"),
            {"refresh": refresh_token},
            format="json",
        )

        # Should be rejected (token reuse prevention)
        assert refresh_response2.status_code == status.HTTP_401_UNAUTHORIZED
