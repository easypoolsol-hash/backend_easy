"""
API endpoints tests.
Tests CRUD operations for all main API resources.
"""

import requests

# Django imports - only import if Django is available
try:
    import os
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bus_kiosk_backend.settings')
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from rest_framework import status
    from rest_framework.test import APITestCase
    DJANGO_AVAILABLE = True
except Exception:
    DJANGO_AVAILABLE = False


# Django test classes - only define if Django is available
if DJANGO_AVAILABLE:
    class TestAPIEndpoints(APITestCase):
        """Test all API endpoints with authentication."""

        def setUp(self):
            """Create test user and get authentication token."""
            from users.models import Role

            # Create required role if it doesn't exist
            role, _ = Role.objects.get_or_create(
                name="backend_engineer",
                defaults={"description": "Backend Engineer Role"}
            )

            user_model = get_user_model()
            self.user = user_model.objects.create_user(
                username='testuser_api',
                email='api@test.com',
                password='testpass123',
                role=role
            )

            # Get JWT token
            token_response = self.client.post('/api/v1/auth/token/', {
                'username': 'testuser_api',
                'password': 'testpass123'
            })
            self.access_token = token_response.data['access']
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        def test_users_endpoints(self):
            """Test users API endpoints."""
            # Test GET users list
            response = self.client.get('/api/v1/users/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('results', response.data)

            # Test GET current user
            response = self.client.get('/api/v1/users/me/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        def test_roles_endpoints(self):
            """Test roles API endpoints."""
            # Test GET roles list
            response = self.client.get('/api/v1/roles/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('results', response.data)

        def test_students_endpoints(self):
            """Test students API endpoints."""
            # Test GET students list
            response = self.client.get('/api/v1/students/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('results', response.data)

        def test_schools_endpoints(self):
            """Test schools API endpoints."""
            # Test GET schools list
            response = self.client.get('/api/v1/schools/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('results', response.data)

        def test_buses_endpoints(self):
            """Test buses API endpoints."""
            # Test GET buses list
            response = self.client.get('/api/v1/buses/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('results', response.data)

        def test_routes_endpoints(self):
            """Test routes API endpoints."""
            # Test GET routes list
            response = self.client.get('/api/v1/routes/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('results', response.data)

        def test_kiosks_endpoints(self):
            """Test kiosks API endpoints."""
            # Test GET kiosks list
            response = self.client.get('/api/v1/kiosks/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('results', response.data)

        def test_boarding_events_endpoints(self):
            """Test boarding events API endpoints."""
            # Test GET boarding events list
            response = self.client.get('/api/v1/boarding-events/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('results', response.data)

        def test_attendance_endpoints(self):
            """Test attendance API endpoints."""
            # Test GET attendance list
            response = self.client.get('/api/v1/attendance/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('results', response.data)

        def test_api_keys_endpoints(self):
            """Test API keys endpoints."""
            # Test GET API keys list
            response = self.client.get('/api/v1/api-keys/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('results', response.data)

        def test_audit_logs_endpoints(self):
            """Test audit logs endpoints."""
            # Test GET audit logs list
            response = self.client.get('/api/v1/audit-logs/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('results', response.data)

        def test_device_logs_endpoints(self):
            """Test device logs endpoints."""
            # Test GET device logs list
            response = self.client.get('/api/v1/logs/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('results', response.data)

        def test_student_photos_endpoints(self):
            """Test student photos endpoints."""
            # Test GET student photos list
            response = self.client.get('/api/v1/student-photos/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('results', response.data)

        def test_parents_endpoints(self):
            """Test parents endpoints."""
            # Test GET parents list
            response = self.client.get('/api/v1/parents/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('results', response.data)

        def test_student_parents_endpoints(self):
            """Test student-parents endpoints."""
            # Test GET student-parents list
            response = self.client.get('/api/v1/student-parents/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('results', response.data)

        def test_face_embeddings_endpoints(self):
            """Test face embeddings endpoints."""
            # Test GET face embeddings list
            response = self.client.get('/api/v1/face-embeddings/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('results', response.data)


class TestAPIEndpointsWithoutAuth:
    """Test that API endpoints require authentication."""

    def test_all_endpoints_require_auth(self):
        """Test that all API endpoints return 401 without authentication."""
        endpoints = [
            '/api/v1/users/',
            '/api/v1/roles/',
            '/api/v1/students/',
            '/api/v1/schools/',
            '/api/v1/buses/',
            '/api/v1/routes/',
            '/api/v1/kiosks/',
            '/api/v1/boarding-events/',
            '/api/v1/attendance/',
            '/api/v1/api-keys/',
            '/api/v1/audit-logs/',
            '/api/v1/logs/',
            '/api/v1/student-photos/',
            '/api/v1/parents/',
            '/api/v1/student-parents/',
            '/api/v1/face-embeddings/',
        ]

        for endpoint in endpoints:
            response = requests.get(f'http://127.0.0.1:8000{endpoint}',
                                  allow_redirects=False)
            assert response.status_code == 401, f"Endpoint {endpoint} should require auth"


if __name__ == '__main__':
    # Run API endpoints tests
    print("Running API Endpoints Tests...")

    # Test endpoints without auth (don't require Django setup)
    test_no_auth = TestAPIEndpointsWithoutAuth()

    try:
        test_no_auth.test_all_endpoints_require_auth()
        print("All endpoints properly require authentication")
    except Exception as e:
        print(f"Authentication requirement test failed: {e}")

    print("API endpoints tests completed!")
