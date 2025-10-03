"""
Health and monitoring endpoint tests.
Tests basic health checks and system monitoring.
"""

import pytest
import requests


class TestHealthEndpoints:
    """Test health check and monitoring endpoints."""

    def test_basic_health_check(self):
        """Test basic health check endpoint."""
        response = requests.get('http://127.0.0.1:8000/health/')
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'

    def test_detailed_health_check(self):
        """Test detailed health check endpoint."""
        response = requests.get('http://127.0.0.1:8000/health/detailed/')
        assert response.status_code == 200
        # Detailed health should return more comprehensive data
        data = response.json()
        assert 'status' in data

    def test_api_root_endpoint(self):
        """Test API root information endpoint."""
        response = requests.get('http://127.0.0.1:8000/api/')
        assert response.status_code == 200
        data = response.json()
        assert 'name' in data
        assert 'version' in data
        assert 'docs' in data
        assert data['name'] == 'Bus Kiosk Backend API'


if __name__ == '__main__':
    # Run basic health checks
    print("Running Health Tests...")

    test_instance = TestHealthEndpoints()

    try:
        test_instance.test_basic_health_check()
        print("Basic health check passed")
    except Exception as e:
        print(f"Basic health check failed: {e}")

    try:
        test_instance.test_detailed_health_check()
        print("Detailed health check passed")
    except Exception as e:
        print(f"Detailed health check failed: {e}")

    try:
        test_instance.test_api_root_endpoint()
        print("API root endpoint passed")
    except Exception as e:
        print(f"API root endpoint failed: {e}")

    print("Health tests completed!")
