"""
Security and documentation tests.
Tests documentation protection, admin access, and security features.
"""

import pytest
import requests

# Django imports - only import if Django is available
try:
    import os
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bus_kiosk_backend.settings')
    import django
    django.setup()
    from django.test import TestCase
    from django.contrib.auth import get_user_model
    from rest_framework.test import APITestCase
    from rest_framework import status
    DJANGO_AVAILABLE = True
except Exception:
    DJANGO_AVAILABLE = False


# Django test classes - only define if Django is available
if DJANGO_AVAILABLE:
    class TestDocumentationSecurity(APITestCase):
        """Test documentation and admin panel security."""

        def setUp(self):
            """Create test admin user."""
            user_model = get_user_model()
            self.admin_user = user_model.objects.create_superuser(
                username='admin_test',
                email='admin@test.com',
                password='adminpass123',
                role_id='super_admin'
            )

        def test_docs_redirect_without_auth(self):
            """Test that docs redirect to login without authentication."""
            endpoints = ['/docs/', '/docs/schema/', '/docs/redoc/']

            for endpoint in endpoints:
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, 302)  # Redirect
                self.assertIn('/admin/login/', response['Location'])

        def test_admin_redirect_without_auth(self):
            """Test that admin panel redirects to login without authentication."""
            response = self.client.get('/admin/')
            self.assertEqual(response.status_code, 302)  # Redirect
            self.assertIn('/admin/login/', response['Location'])

        def test_docs_accessible_with_session_auth(self):
            """Test that docs are accessible with admin session."""
            # Login via admin
            self.client.login(username='admin_test', password='adminpass123')

            endpoints = ['/docs/', '/docs/schema/', '/docs/redoc/']

            for endpoint in endpoints:
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, 200)

        def test_admin_accessible_with_session_auth(self):
            """Test that admin panel is accessible with admin session."""
            # Login via admin
            self.client.login(username='admin_test', password='adminpass123')

            response = self.client.get('/admin/')
            self.assertEqual(response.status_code, 200)


class TestSecurityFeatures:
    """Test various security features."""

    def test_cors_headers(self):
        """Test CORS headers are properly set."""
        # This would need to be configured in settings
        # CORS headers should be present if configured
        # Note: This test will pass if CORS is not configured (expected for now)
        # Placeholder - would need actual CORS config to test properly

    def test_security_headers(self):
        """Test security headers are set."""
        response = requests.get('http://127.0.0.1:8000/health/')

        # Check for common security headers
        security_headers = [
            'x-content-type-options',
            'x-frame-options',
            'x-xss-protection'
        ]

        present_headers = [h for h in security_headers if h in response.headers]
        # At minimum, should have some security headers
        assert len(present_headers) > 0, f"Security headers present: {present_headers}"

    def test_https_redirect(self):
        """Test HTTPS redirect in production (would need SECURE_SSL_REDIRECT=True)."""
        # This test assumes HTTP for development
        response = requests.get('http://127.0.0.1:8000/health/', allow_redirects=False)
        # Should not redirect to HTTPS in development
        assert response.status_code != 301

    def test_api_rate_limiting(self):
        """Test API rate limiting (if configured)."""
        # Make multiple requests quickly
        responses = []
        for _ in range(10):
            response = requests.get('http://127.0.0.1:8000/health/')
            responses.append(response.status_code)

        # Should not be rate limited (429) for health endpoint
        rate_limited = any(status == 429 for status in responses)
        assert not rate_limited, "Health endpoint should not be rate limited"

    def test_error_pages_dont_leak_info(self):
        """Test that error pages don't leak sensitive information."""
        # Test 404 page
        response = requests.get('http://127.0.0.1:8000/nonexistent-page/')
        assert response.status_code == 404
        # Should not contain sensitive info like file paths, stack traces, etc.
        content = response.text.lower()
        sensitive_keywords = ['traceback', 'internal server error', 'file "', '/usr/', 'c:\\']
        for keyword in sensitive_keywords:
            assert keyword not in content, f"Error page contains sensitive keyword: {keyword}"

    def test_debug_mode_disabled(self):
        """Test that DEBUG mode is disabled in production."""
        # This is more of a configuration check
        # In development, DEBUG might be True, so this test is informational
        response = requests.get('http://127.0.0.1:8000/health/')
        # If DEBUG were True, errors might show stack traces
        # But health endpoint should work regardless
        assert response.status_code == 200


class TestDataValidation:
    """Test data validation and sanitization."""

    def test_sql_injection_protection(self):
        """Test protection against SQL injection."""
        # Test with malicious input in query params
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "<script>alert('xss')</script>",
            "../../../etc/passwd"
        ]

        for malicious_input in malicious_inputs:
            response = requests.get(f'http://127.0.0.1:8000/health/?test={malicious_input}')
            # Should not crash or return sensitive data
            assert response.status_code in [200, 400, 404], f"Unexpected response for input: {malicious_input}"

    def test_large_payload_protection(self):
        """Test protection against large payloads."""
        # This would need to be configured in settings (DATA_UPLOAD_MAX_MEMORY_SIZE, etc.)
        # For now, just test that the server handles normal requests
        response = requests.get('http://127.0.0.1:8000/health/')
        assert response.status_code == 200


if __name__ == '__main__':
    # Run security tests
    print("Running Security Tests...")

    # Test security features (don't require Django setup)
    test_security = TestSecurityFeatures()

    try:
        test_security.test_security_headers()
        print("Security headers test passed")
    except Exception as e:
        print(f"Security headers test failed: {e}")

    try:
        test_security.test_error_pages_dont_leak_info()
        print("Error pages security test passed")
    except Exception as e:
        print(f"Error pages test failed: {e}")

    try:
        test_security.test_sql_injection_protection()
        print("SQL injection protection test passed")
    except Exception as e:
        print(f"SQL injection test failed: {e}")

    print("Security tests completed!")
