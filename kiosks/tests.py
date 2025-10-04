from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from users.models import Role, User

from .factories import BusFactory, DeviceLogFactory, KioskFactory
from .models import DeviceLog
from .serializers import (
    KioskHeartbeatSerializer,
    KioskSerializer,
    KioskStatusSerializer,
)


class KioskModelTest(TestCase):
    """Test Kiosk model functionality"""

    def setUp(self):
        """Set up test data"""
        self.bus = BusFactory()
        self.kiosk = KioskFactory(bus=self.bus)

    def test_kiosk_creation(self):
        """Test creating a kiosk"""
        bus = BusFactory()
        kiosk = KioskFactory(
            kiosk_id="KIOSK-001",
            bus=bus,
            api_key_hash="hashed_key_123",
            firmware_version="1.0.0",
            battery_level=85.5,
            storage_used_mb=1024.5
        )

        self.assertEqual(kiosk.kiosk_id, "KIOSK-001")
        self.assertEqual(kiosk.bus, bus)
        self.assertEqual(kiosk.firmware_version, "1.0.0")
        self.assertEqual(kiosk.battery_level, 85.5)
        self.assertEqual(kiosk.storage_used_mb, 1024.5)
        self.assertTrue(kiosk.is_active)
        self.assertIsNotNone(kiosk.created_at)

    def test_kiosk_online_status(self):
        """Test kiosk online status calculation"""
        # Test online kiosk (heartbeat within 5 minutes)
        self.assertTrue(self.kiosk.is_online)

        # Test offline kiosk (no heartbeat) - create new bus and kiosk
        offline_kiosk = KioskFactory(last_heartbeat=None)
        self.assertFalse(offline_kiosk.is_online)

        # Test offline kiosk (old heartbeat) - create new bus and kiosk
        old_kiosk = KioskFactory(last_heartbeat=timezone.now() - timedelta(minutes=10))
        self.assertFalse(old_kiosk.is_online)

    def test_kiosk_string_representation(self):
        """Test kiosk string representation"""
        bus = BusFactory(license_plate="TEST-001")
        kiosk = KioskFactory(kiosk_id="KIOSK-001", bus=bus)
        self.assertEqual(str(kiosk), "KIOSK-001 on TEST-001")


class DeviceLogModelTest(TestCase):
    """Test DeviceLog model functionality"""

    def setUp(self):
        """Set up test data"""
        self.bus = BusFactory()
        self.kiosk = KioskFactory(bus=self.bus)

    def test_device_log_creation(self):
        """Test creating a device log"""
        log = DeviceLogFactory(
            kiosk=self.kiosk,
            log_level="INFO",
            message="Test message",
            metadata={"key": "value"}
        )

        self.assertEqual(log.kiosk, self.kiosk)
        self.assertEqual(log.log_level, "INFO")
        self.assertEqual(log.message, "Test message")
        self.assertEqual(log.metadata, {"key": "value"})
        self.assertIsNotNone(log.timestamp)
        self.assertIsNotNone(log.log_id)

    def test_device_log_string_representation(self):
        """Test device log string representation"""
        log = DeviceLogFactory(
            kiosk=self.kiosk,
            log_level="ERROR",
            message="Error occurred"
        )
        expected = f"[{log.timestamp}] {self.kiosk.kiosk_id} ERROR: Error occurred..."
        self.assertEqual(str(log), expected)


class KioskSerializerTest(TestCase):
    """Test Kiosk serializers"""

    def setUp(self):
        """Set up test data"""
        self.bus = BusFactory()
        self.kiosk = KioskFactory(
            bus=self.bus,
            firmware_version="1.0.0",
            battery_level=85.5
        )

    def test_kiosk_serializer(self):
        """Test KioskSerializer"""
        serializer = KioskSerializer(self.kiosk)
        data = serializer.data

        self.assertEqual(data['kiosk_id'], self.kiosk.kiosk_id)
        self.assertEqual(data['bus'], str(self.bus.bus_id))  # UUID field
        self.assertEqual(data['firmware_version'], "1.0.0")
        self.assertEqual(data['battery_level'], 85.5)
        self.assertIn('is_online', data)
        self.assertIn('created_at', data)

    def test_kiosk_status_serializer(self):
        """Test KioskStatusSerializer with summary data"""
        # This serializer is for output, not input validation
        summary_data = {
            'total_kiosks': 1,
            'active_kiosks': 1,
            'online_kiosks': 1,
            'offline_kiosks': 0,
            'kiosks': [self.kiosk]
        }
        serializer = KioskStatusSerializer(summary_data)
        data = serializer.data

        # Check that the serialized data is correct
        self.assertEqual(data['total_kiosks'], 1)
        self.assertEqual(data['active_kiosks'], 1)
        self.assertEqual(data['online_kiosks'], 1)
        self.assertEqual(data['offline_kiosks'], 0)
        self.assertEqual(len(data['kiosks']), 1)

    def test_kiosk_heartbeat_serializer_valid(self):
        """Test KioskHeartbeatSerializer with valid data"""
        # Create a kiosk for validation
        bus = BusFactory()
        kiosk = KioskFactory(bus=bus, api_key_hash="test_key")

        data = {
            "kiosk_id": kiosk.kiosk_id,  # Use the actual kiosk_id from factory
            "firmware_version": "1.0.1",
            "battery_level": 90.0,
            "storage_used_mb": 512.0
        }
        serializer = KioskHeartbeatSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_kiosk_heartbeat_serializer_invalid(self):
        """Test KioskHeartbeatSerializer with invalid data"""
        data = {
            "kiosk_id": "",  # Invalid empty kiosk_id
            "battery_level": 150.0  # Invalid battery level > 100
        }
        serializer = KioskHeartbeatSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('kiosk_id', serializer.errors)
        self.assertIn('battery_level', serializer.errors)


class KioskAPITest(APITestCase):
    """Test Kiosk API endpoints"""

    def setUp(self):
        """Set up test data and client"""
        self.client = APIClient()
        self.bus = BusFactory()
        self.kiosk = KioskFactory(
            bus=self.bus,
            api_key_hash="hashed_key_123",
            firmware_version="1.0.0"
        )

    def test_kiosk_list(self):
        """Test listing kiosks"""
        # Create an authenticated user for read access
        role = Role.objects.create(name='backend_engineer')
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass',
            role=role
        )
        self.client.force_authenticate(user=user)

        url = reverse('kiosk-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['kiosk_id'], self.kiosk.kiosk_id)

    def test_kiosk_detail(self):
        """Test retrieving kiosk detail"""
        # Create an authenticated user for read access
        role = Role.objects.create(name='backend_engineer')
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass',
            role=role
        )
        self.client.force_authenticate(user=user)

        url = reverse('kiosk-detail', kwargs={'pk': self.kiosk.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['kiosk_id'], self.kiosk.kiosk_id)

    def test_kiosk_heartbeat(self):
        """Test kiosk heartbeat endpoint"""
        url = reverse('kiosk-heartbeat')
        data = {
            "kiosk_id": self.kiosk.kiosk_id,
            "firmware_version": "1.0.1",
            "battery_level": 90.0,
            "storage_used_mb": 512.0
        }
        # Add kiosk API key header
        response = self.client.post(url, data, format='json', **{'HTTP_X_KIOSK_API_KEY': self.kiosk.api_key_hash})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)
        self.assertIn('timestamp', response.data)

        # Verify kiosk was updated
        self.kiosk.refresh_from_db()
        self.assertEqual(self.kiosk.firmware_version, "1.0.1")
        self.assertEqual(self.kiosk.battery_level, 90.0)

    def test_kiosk_heartbeat_invalid_kiosk(self):
        """Test kiosk heartbeat with invalid kiosk_id"""
        url = reverse('kiosk-heartbeat')
        data = {
            "kiosk_id": "INVALID-KIOSK",
            "firmware_version": "1.0.1",
            "battery_level": 90.0
        }
        # Add invalid API key
        response = self.client.post(url, data, format='json', **{'HTTP_X_KIOSK_API_KEY': 'invalid_key'})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_kiosk_log(self):
        """Test kiosk logging endpoint"""
        url = reverse('kiosk-log')
        data = {
            "kiosk_id": self.kiosk.kiosk_id,
            "logs": [
                {
                    "log_level": "INFO",
                    "message": "Test log message",
                    "metadata": {"test": True}
                }
            ]
        }
        # Add kiosk API key header
        response = self.client.post(url, data, format='json', **{'HTTP_X_KIOSK_API_KEY': self.kiosk.api_key_hash})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('logged_count', response.data)
        self.assertEqual(response.data['logged_count'], 1)

        # Verify log was created
        log = DeviceLog.objects.first()
        self.assertEqual(log.kiosk, self.kiosk)
        self.assertEqual(log.log_level, "INFO")
        self.assertEqual(log.message, "Test log message")

    def test_kiosk_log_invalid_kiosk(self):
        """Test kiosk logging with invalid kiosk_id"""
        url = reverse('kiosk-log')
        data = {
            "kiosk_id": "INVALID-KIOSK",
            "logs": [
                {
                    "log_level": "ERROR",
                    "message": "Test error"
                }
            ]
        }
        # Add invalid API key
        response = self.client.post(url, data, format='json', **{'HTTP_X_KIOSK_API_KEY': 'invalid_key'})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DeviceLogAPITest(APITestCase):
    """Test DeviceLog API endpoints"""

    def setUp(self):
        """Set up test data and client"""
        self.client = APIClient()
        self.bus = BusFactory()
        self.kiosk = KioskFactory(bus=self.bus)
        self.log = DeviceLogFactory(kiosk=self.kiosk, log_level="INFO", message="Test log")

    def test_device_log_list(self):
        """Test listing device logs"""
        # Create an authenticated user for read access
        role = Role.objects.create(name='backend_engineer')
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass',
            role=role
        )
        self.client.force_authenticate(user=user)

        url = reverse('device-log-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['log_level'], "INFO")

    def test_device_log_detail(self):
        """Test retrieving device log detail"""
        # Create an authenticated user for read access
        role = Role.objects.create(name='backend_engineer')
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass',
            role=role
        )
        self.client.force_authenticate(user=user)

        url = reverse('device-log-detail', kwargs={'pk': self.log.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], "Test log")

    def test_device_log_filtering(self):
        """Test device log filtering by kiosk"""
        # Create another bus and kiosk for testing filtering
        bus2 = BusFactory()
        kiosk2 = KioskFactory(bus=bus2, api_key_hash="unique_key_456")
        DeviceLogFactory(kiosk=kiosk2, log_level="ERROR", message="Error log")

        # Create an authenticated user for read access
        role = Role.objects.create(name='backend_engineer')
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass',
            role=role
        )
        self.client.force_authenticate(user=user)

        url = reverse('device-log-list')
        response = self.client.get(url, {'kiosk': self.kiosk.kiosk_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['log_level'], "INFO")
