"""
Authentication and authorization tests.
Tests JWT token generation, validation, and protected endpoints.
"""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase


class TestAuthentication(APITestCase):
    """Test JWT authentication system."""

    def setUp(self):
        """Create test user for authentication tests."""
        from users.models import Role

        # Create required role if it doesn't exist
        role, _ = Role.objects.get_or_create(
            name="backend_engineer", defaults={"description": "Backend Engineer Role"}
        )

        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="testuser_auth",
            email="auth@test.com",
            password="testpass123",
            role=role,
        )

    def test_jwt_token_generation(self):
        """Test JWT access and refresh token generation."""
        response = self.client.post(
            "/api/v1/auth/token/",
            {"username": "testuser_auth", "password": "testpass123"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        # Verify tokens are strings and not empty
        access_token = response.data["access"]
        refresh_token = response.data["refresh"]
        self.assertIsInstance(access_token, str)
        self.assertIsInstance(refresh_token, str)
        self.assertGreater(len(access_token), 0)
        self.assertGreater(len(refresh_token), 0)

    def test_jwt_token_refresh(self):
        """Test JWT token refresh functionality."""
        # First get tokens
        token_response = self.client.post(
            "/api/v1/auth/token/",
            {"username": "testuser_auth", "password": "testpass123"},
        )
        refresh_token = token_response.data["refresh"]

        # Then refresh
        refresh_response = self.client.post(
            "/api/v1/auth/token/refresh/", {"refresh": refresh_token}
        )

        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh_response.data)

    def test_invalid_credentials(self):
        """Test authentication with invalid credentials."""
        response = self.client.post(
            "/api/v1/auth/token/",
            {"username": "testuser_auth", "password": "wrongpassword"},
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TestProtectedEndpoints(APITestCase):
    """Test that protected endpoints require authentication."""

    def test_docs_endpoints_protected(self):
        """Test that documentation endpoints redirect to login."""
        endpoints = ["/docs/", "/docs/schema/", "/docs/redoc/"]

        for endpoint in endpoints:
            response = self.client.get(endpoint, follow=False)
            self.assertEqual(response.status_code, 302)  # Redirect to login
            self.assertIn("login", response["Location"])

    def test_admin_panel_protected(self):
        """Test that admin panel is protected."""
        response = self.client.get("/admin/", follow=False)
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_api_endpoints_require_auth(self):
        """Test that API endpoints return 401 without authentication."""
        endpoints = [
            "/api/v1/students/",
            "/api/v1/buses/",
            "/api/v1/kiosks/",
            "/api/v1/boarding-events/",
            "/api/v1/attendance/",
        ]

        for endpoint in endpoints:
            response = self.client.get(endpoint)
            # Should return 401 Unauthorized (not redirect for API endpoints)
            self.assertEqual(response.status_code, 401)
