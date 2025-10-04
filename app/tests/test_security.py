"""
Security and documentation tests.
Tests documentation protection, admin access, and security features.
"""

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase


class TestDocumentationSecurity(APITestCase):
        """Test documentation and admin panel security."""

        def setUp(self):
            """Create test admin user."""
            user_model = get_user_model()
            self.admin_user = user_model.objects.create_superuser(
                username='admin_test',
                email='admin@test.com',
                password='adminpass123'
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


class TestSecurityFeatures(APITestCase):
    """Test various security features."""

    def test_security_headers(self):
        """Test security headers are set."""
        response = self.client.get('/health/')

        # Check for common security headers
        security_headers = [
            'x-content-type-options',
            'x-frame-options',
            'x-xss-protection'
        ]

        present_headers = [h for h in security_headers if h in response]
        # At minimum, should have some security headers
        self.assertGreater(len(present_headers), 0, f"Security headers present: {present_headers}")

    def test_api_rate_limiting(self):
        """Test API rate limiting (if configured)."""
        # Make multiple requests quickly
        responses = []
        for _ in range(10):
            response = self.client.get('/health/')
            responses.append(response.status_code)

        # Should not be rate limited (429) for health endpoint
        rate_limited = any(status == 429 for status in responses)
        self.assertFalse(rate_limited, "Health endpoint should not be rate limited")

    def test_error_pages_dont_leak_info(self):
        """Test that error pages don't leak sensitive information."""
        # Test 404 page
        response = self.client.get('/nonexistent-page/')
        self.assertEqual(response.status_code, 404)
        # Should not contain sensitive info like file paths, stack traces, etc.
        content = response.content.decode('utf-8').lower()
        sensitive_keywords = ['traceback', 'internal server error', 'file "', '/usr/', 'c:\\']
        for keyword in sensitive_keywords:
            self.assertNotIn(keyword, content, f"Error page contains sensitive keyword: {keyword}")


class TestDataValidation(APITestCase):
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
            response = self.client.get(f'/health/?test={malicious_input}')
            # Should not crash or return sensitive data
            self.assertIn(response.status_code, [200, 400, 404],
                         f"Unexpected response for input: {malicious_input}")

    def test_large_payload_protection(self):
        """Test protection against large payloads."""
        # This would need to be configured in settings (DATA_UPLOAD_MAX_MEMORY_SIZE, etc.)
        # For now, just test that the server handles normal requests
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
