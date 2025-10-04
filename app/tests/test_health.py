"""
Health and monitoring endpoint tests.
Tests basic health checks and system monitoring.
"""

from rest_framework.test import APITestCase


class TestHealthEndpoints(APITestCase):
    """Test health check and monitoring endpoints."""

    def test_basic_health_check(self):
        """Test basic health check endpoint."""
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'healthy')

    def test_detailed_health_check(self):
        """Test detailed health check endpoint."""
        response = self.client.get('/health/detailed/')
        self.assertEqual(response.status_code, 200)
        # Detailed health should return more comprehensive data
        data = response.json()
        self.assertIn('status', data)

    def test_api_root_endpoint(self):
        """Test API root information endpoint."""
        response = self.client.get('/api/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('name', data)
        self.assertIn('version', data)
        self.assertIn('docs', data)
        self.assertEqual(data['name'], 'Bus Kiosk Backend API')
