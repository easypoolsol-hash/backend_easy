from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status

from students.models import Student, School
from users.models import Role, User

from .models import Bus, Route


class RouteModelTest(TestCase):
    """Test cases for Route model"""

    def test_route_creation(self):
        """Test creating a route with stops and schedule"""
        stops = [
            {"name": "School", "lat": 40.7128, "lon": -74.0060, "sequence": 1, "estimated_time": "08:00"},
            {"name": "Stop 1", "lat": 40.7589, "lon": -73.9851, "sequence": 2, "estimated_time": "08:15"}
        ]
        schedule = {
            "morning": {"start": "07:30", "end": "08:30"},
            "afternoon": {"start": "15:00", "end": "16:00"}
        }

        route = Route.objects.create(
            name="Test Route",
            description="A test route",
            stops=stops,
            schedule=schedule
        )

        self.assertEqual(route.name, "Test Route")
        self.assertEqual(len(route.stops), 2)
        self.assertEqual(route.stop_count, 2)
        self.assertTrue(route.is_active)


class BusModelTest(TestCase):
    """Test cases for Bus model"""

    def setUp(self):
        self.route = Route.objects.create(
            name="Test Route",
            stops=[{"name": "Stop 1", "lat": 0, "lon": 0, "sequence": 1}]
        )
        self.school = School.objects.create(name='Test School')

    def test_bus_creation(self):
        """Test creating a bus"""
        bus = Bus.objects.create(
            license_plate="ABC-123",
            route=self.route,
            capacity=50,
            manufacturer="Test Manufacturer",
            model="Test Model",
            year=2020
        )

        self.assertEqual(bus.license_plate, "ABC-123")
        self.assertEqual(bus.capacity, 50)
        self.assertEqual(bus.status, 'active')
        self.assertTrue(bus.is_available)

    def test_bus_utilization(self):
        """Test bus utilization calculation"""
        bus = Bus.objects.create(
            license_plate="XYZ-789",
            capacity=10
        )

        # Initially no students assigned
        self.assertEqual(bus.assigned_students_count, 0)
        self.assertEqual(bus.utilization_percentage, 0)

        # Create and assign students
        students = []
        for i in range(7):  # 70% utilization
            student = Student.objects.create(
                school=self.school,
                name=f"Student {i}",
                grade="5",
                section="A",
                enrollment_date=timezone.now().date(),
                assigned_bus=bus
            )
            students.append(student)

        bus.refresh_from_db()
        self.assertEqual(bus.assigned_students_count, 7)
        self.assertEqual(bus.utilization_percentage, 70.0)


class RouteAPITest(APITestCase):
    """Test cases for Route API"""

    def setUp(self):
        role = Role.objects.create(name='school_admin')
        self.user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='admin123',
            role=role
        )
        self.client.force_authenticate(user=self.user)

    def test_create_route(self):
        """Test creating a route via API"""
        data = {
            'name': 'API Test Route',
            'description': 'Created via API',
            'stops': [
                {'name': 'Start', 'lat': 40.7128, 'lon': -74.0060, 'sequence': 1}
            ],
            'schedule': {
                'morning': {'start': '08:00', 'end': '09:00'}
            }
        }

        response = self.client.post('/api/v1/routes/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'API Test Route')


class BusAPITest(APITestCase):
    """Test cases for Bus API"""

    def setUp(self):
        role = Role.objects.create(name='school_admin')
        self.user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='admin123',
            role=role
        )
        self.route = Route.objects.create(name="Test Route")
        self.client.force_authenticate(user=self.user)

    def test_create_bus(self):
        """Test creating a bus via API"""
        data = {
            'license_plate': 'TEST-001',
            'route': str(self.route.route_id),
            'capacity': 45,
            'manufacturer': 'Test Co',
            'model': 'Model X',
            'year': 2022
        }

        response = self.client.post('/api/v1/buses/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['license_plate'], 'TEST-001')
