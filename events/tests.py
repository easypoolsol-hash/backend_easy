from django.test import TestCase
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.test import APITestCase

from buses.models import Bus
from kiosks.models import Kiosk
from students.models import School, Student
from users.models import Role, User

from .models import AttendanceRecord, BoardingEvent


class BoardingEventModelTest(TestCase):
    """Test cases for BoardingEvent model"""

    def setUp(self):
        self.role = Role.objects.create(name='school_admin')
        self.school = School.objects.create(name='Test School')
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role=self.role
        )
        self.student = Student.objects.create(
            school=self.school,
            name='Test Student',
            grade='5',
            section='A',
            enrollment_date=timezone.now().date()
        )

    def test_ulid_generation(self):
        """Test that ULID is auto-generated"""
        event = BoardingEvent.objects.create(
            student=self.student,
            kiosk_id='KIOSK001',
            confidence_score=0.95,
            timestamp=timezone.now(),
            model_version='v1.0'
        )
        self.assertIsNotNone(event.event_id)
        self.assertEqual(len(event.event_id), 26)  # ULID length

    def test_confidence_score_validation(self):
        """Test confidence score validation"""
        # Valid score - just create and save
        event = BoardingEvent.objects.create(
            student=self.student,
            kiosk_id='KIOSK001',
            confidence_score=0.8,
            timestamp=timezone.now(),
            model_version='v1.0',
            metadata={}
        )
        self.assertEqual(event.confidence_score, 0.8)

        # Invalid scores
        with self.assertRaises(serializers.ValidationError):
            invalid_event = BoardingEvent(
                student=self.student,
                kiosk_id='KIOSK001',
                confidence_score=-0.1,
                timestamp=timezone.now(),
                model_version='v1.0',
                metadata={}
            )
            invalid_event.full_clean()

        with self.assertRaises(serializers.ValidationError):
            invalid_event = BoardingEvent(
                student=self.student,
                kiosk_id='KIOSK001',
                confidence_score=1.1,
                timestamp=timezone.now(),
                model_version='v1.0',
                metadata={}
            )
            invalid_event.full_clean()


class AttendanceRecordModelTest(TestCase):
    """Test cases for AttendanceRecord model"""

    def setUp(self):
        self.school = School.objects.create(name='Test School')
        self.student = Student.objects.create(
            school=self.school,
            name='Test Student',
            grade='5',
            section='A',
            enrollment_date=timezone.now().date()
        )

    def test_status_calculation(self):
        """Test automatic status calculation"""
        # Present (both sessions)
        record = AttendanceRecord.objects.create(
            student=self.student,
            date=timezone.now().date(),
            morning_boarded=True,
            afternoon_boarded=True
        )
        self.assertEqual(record.status, 'present')

        # Absent (no sessions)
        record2 = AttendanceRecord.objects.create(
            student=self.student,
            date=timezone.now().date() - timezone.timedelta(days=1),
            morning_boarded=False,
            afternoon_boarded=False
        )
        self.assertEqual(record2.status, 'absent')

        # Partial (one session)
        record3 = AttendanceRecord.objects.create(
            student=self.student,
            date=timezone.now().date() - timezone.timedelta(days=2),
            morning_boarded=True,
            afternoon_boarded=False
        )
        self.assertEqual(record3.status, 'partial')


class BoardingEventAPITest(APITestCase):
    """Test cases for BoardingEvent API"""

    def setUp(self):
        self.school = School.objects.create(name='Test School')
        self.bus = Bus.objects.create(
            license_plate='TEST-001',
            capacity=50
        )
        self.kiosk = Kiosk.objects.create(
            bus=self.bus,
            kiosk_id='KIOSK001',
            api_key_hash='test_kiosk_key_123'
        )
        self.student = Student.objects.create(
            school=self.school,
            name='Test Student',
            grade='5',
            section='A',
            enrollment_date=timezone.now().date()
        )

    def test_create_boarding_event(self):
        """Test creating a boarding event"""
        data = {
            'student': str(self.student.student_id),
            'kiosk_id': 'KIOSK001',
            'confidence_score': 0.95,
            'timestamp': timezone.now().isoformat(),
            'model_version': 'v1.0'
        }

        response = self.client.post('/api/v1/boarding-events/', data, format='json', **{'HTTP_X_KIOSK_API_KEY': self.kiosk.api_key_hash})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('event_id', response.data)

    def test_bulk_create_events(self):
        """Test bulk creating boarding events"""
        events_data = [
            {
                'student': str(self.student.student_id),
                'kiosk_id': 'KIOSK001',
                'confidence_score': 0.95,
                'timestamp': timezone.now().isoformat(),
                'model_version': 'v1.0'
            },
            {
                'student': str(self.student.student_id),
                'kiosk_id': 'KIOSK001',
                'confidence_score': 0.92,
                'timestamp': (timezone.now() - timezone.timedelta(minutes=5)).isoformat(),
                'model_version': 'v1.0'
            }
        ]

        response = self.client.post('/api/v1/boarding-events/bulk/', events_data, format='json', **{'HTTP_X_KIOSK_API_KEY': self.kiosk.api_key_hash})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created'], 2)
