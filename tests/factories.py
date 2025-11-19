"""
Test Data Factories (Fortune 500 pattern using Factory Boy)

Instead of creating test data manually, use factories.
This reduces code duplication and makes tests cleaner.

Example:
    # Before (manual):
    school = School.objects.create(name="Test School")
    bus = Bus.objects.create(license_plate="TEST-001", ...)

    # After (factory):
    school = SchoolFactory()
    bus = BusFactory()
"""

from datetime import date

from cryptography.fernet import Fernet
from django.conf import settings
from django.utils import timezone
import factory
from factory.django import DjangoModelFactory

from buses.models import Bus, Route, RouteWaypoint, Waypoint
from kiosks.models import Kiosk
from notifications.models import FCMToken, Notification, NotificationPreference
from students.models import (
    FaceEmbeddingMetadata,
    FaceEnrollment,
    Parent,
    School,
    Student,
    StudentParent,
    StudentPhoto,
)
from users.models import User


class SchoolFactory(DjangoModelFactory):
    """Factory for creating test schools"""

    class Meta:
        model = School
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"Test School {n}")


class RouteFactory(DjangoModelFactory):
    """Factory for creating test routes"""

    class Meta:
        model = Route

    name = factory.Sequence(lambda n: f"Test Route {n}")
    description = ""
    created_at = factory.LazyFunction(timezone.now)
    encoded_polyline = ""


class WaypointFactory(DjangoModelFactory):
    """Factory for creating test waypoints"""

    class Meta:
        model = Waypoint

    latitude = factory.Faker("latitude")
    longitude = factory.Faker("longitude")
    metadata = factory.Dict({"type": "bus_stop", "name": factory.Sequence(lambda n: f"Waypoint {n}")})


class PathAdjustmentWaypointFactory(WaypointFactory):
    """Factory for creating path adjustment waypoints"""

    metadata = factory.Dict({"type": "path_adjustment", "note": "Route adjustment point"})


class RouteWaypointFactory(DjangoModelFactory):
    """Factory for creating route waypoint junctions"""

    class Meta:
        model = RouteWaypoint

    route = factory.SubFactory(RouteFactory)
    waypoint = factory.SubFactory(WaypointFactory)
    sequence = factory.Sequence(lambda n: n + 1)


class BusFactory(DjangoModelFactory):
    """Factory for creating test buses"""

    class Meta:
        model = Bus

    bus_number = factory.Sequence(lambda n: f"BUS-{n:03d}")
    license_plate = factory.Sequence(lambda n: f"TEST-BUS-{n:03d}")
    route = factory.SubFactory(RouteFactory)
    capacity = 40
    status = "active"


class KioskFactory(DjangoModelFactory):
    """
    Factory for creating test kiosks

    Usage:
        # Create kiosk with default settings (inactive)
        kiosk = KioskFactory()

        # Create active kiosk
        kiosk = KioskFactory(is_active=True)

        # Access activation token (generated automatically)
        token = kiosk._activation_token
    """

    class Meta:
        model = Kiosk

    kiosk_id = factory.Sequence(lambda n: f"TEST-KIOSK-{n:03d}")
    bus = factory.SubFactory(BusFactory)
    is_active = False  # Kiosks start inactive now


class StudentFactory(DjangoModelFactory):
    """
    Factory for creating test students with encrypted names

    Usage:
        # Create with default encrypted name
        student = StudentFactory()

        # Create with specific name (will be encrypted)
        student = StudentFactory(plaintext_name="John Doe")

        # Access encrypted name
        encrypted = student.name

        # Access plaintext (stored as trait)
        plaintext = student._plaintext_name
    """

    class Meta:
        model = Student
        skip_postgeneration_save = True

    school_student_id = factory.Sequence(lambda n: f"STU-TEST-{n:05d}")
    school = factory.SubFactory(SchoolFactory)
    grade = "5"
    section = "A"
    assigned_bus = factory.SubFactory(BusFactory)
    status = "active"
    enrollment_date = date(2024, 1, 15)

    class Params:
        plaintext_name = "Test Student"

    @factory.lazy_attribute  # type: ignore[arg-type]
    def name(self):
        """Encrypt the student name"""
        fernet = Fernet(settings.ENCRYPTION_KEY.encode())
        plaintext = self.plaintext_name if hasattr(self, "plaintext_name") else "Test Student"
        return fernet.encrypt(plaintext.encode()).decode()

    @factory.post_generation
    def store_plaintext_name(self, create, extracted, **kwargs):
        """Store plaintext name for test access after creation"""
        if not create:
            return
        self._plaintext_name = self.plaintext_name if hasattr(self, "plaintext_name") else "Test Student"


class ParentFactory(DjangoModelFactory):
    """
    Factory for creating test parents with encrypted PII

    Usage:
        # Create with defaults
        parent = ParentFactory()

        # Create with specific data (will be encrypted)
        parent = ParentFactory(
            plaintext_name="Mr. Sharma",
            plaintext_email="sharma@example.com",
            plaintext_phone="+919876543210"
        )

        # Access plaintext (stored as traits)
        name = parent._plaintext_name
        email = parent._plaintext_email
        phone = parent._plaintext_phone
    """

    class Meta:
        model = Parent

    class Params:
        plaintext_name = factory.Sequence(lambda n: f"Test Parent {n}")
        plaintext_email = factory.Sequence(lambda n: f"parent{n}@example.com")
        plaintext_phone = factory.Sequence(lambda n: f"+9198765432{n:02d}")

    @factory.lazy_attribute  # type: ignore[arg-type]
    def name(self):
        """Encrypt parent name"""
        fernet = Fernet(settings.ENCRYPTION_KEY.encode())
        plaintext = self.plaintext_name if hasattr(self, "plaintext_name") else "Test Parent"
        return fernet.encrypt(plaintext.encode()).decode()

    @factory.lazy_attribute  # type: ignore[arg-type]
    def email(self):
        """Encrypt parent email"""
        fernet = Fernet(settings.ENCRYPTION_KEY.encode())
        plaintext = self.plaintext_email if hasattr(self, "plaintext_email") else "test@example.com"
        return fernet.encrypt(plaintext.encode()).decode()

    @factory.lazy_attribute  # type: ignore[arg-type]
    def phone(self):
        """Encrypt parent phone"""
        fernet = Fernet(settings.ENCRYPTION_KEY.encode())
        plaintext = self.plaintext_phone if hasattr(self, "plaintext_phone") else "+919876543210"
        return fernet.encrypt(plaintext.encode()).decode()

    @factory.post_generation
    def store_plaintext_pii(self, create, extracted, **kwargs):
        """Store plaintext PII for test access after creation"""
        if not create:
            return
        self._plaintext_name = self.plaintext_name if hasattr(self, "plaintext_name") else "Test Parent"
        self._plaintext_email = self.plaintext_email if hasattr(self, "plaintext_email") else "test@example.com"
        self._plaintext_phone = self.plaintext_phone if hasattr(self, "plaintext_phone") else "+919876543210"


class StudentParentFactory(DjangoModelFactory):
    """Factory for creating student-parent relationships"""

    class Meta:
        model = StudentParent

    student = factory.SubFactory(StudentFactory)
    parent = factory.SubFactory(ParentFactory)
    relationship = "father"
    is_primary = True


class UserFactory(DjangoModelFactory):
    """Factory for creating test users"""

    class Meta:
        model = User

    # user_id auto-generates as UUID via model default
    username = factory.Sequence(lambda n: f"testuser{n}")
    email = factory.Sequence(lambda n: f"user{n}@test.com")
    created_at = factory.LazyFunction(timezone.now)

    @factory.post_generation
    def groups(self, create, extracted, **kwargs):
        """Assign default group after creation"""
        if not create:
            return
        from django.contrib.auth.models import Group

        default_group, _ = Group.objects.get_or_create(name="Backend Engineer")
        self.groups.add(default_group)

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        """Set password after creation"""
        if not create:
            return
        password = extracted if extracted else "testpass123"
        self.set_password(password)  # type: ignore[attr-defined]
        self.save()  # type: ignore[attr-defined]


class StudentPhotoFactory(DjangoModelFactory):
    """Factory for creating test student photos with binary data"""

    class Meta:
        model = StudentPhoto

    student = factory.SubFactory(StudentFactory)
    is_primary = True

    @factory.lazy_attribute  # type: ignore[arg-type]
    def photo_data(self):
        """Generate fake photo binary data"""
        from io import BytesIO

        from PIL import Image

        # Create a simple 100x100 blue image
        img = Image.new("RGB", (100, 100), color="blue")
        buffer = BytesIO()
        img.save(buffer, format="JPEG")
        return buffer.getvalue()

    photo_content_type = "image/jpeg"


class FaceEmbeddingMetadataFactory(DjangoModelFactory):
    """
    Factory for creating test face embedding metadata
    """

    class Meta:
        model = FaceEmbeddingMetadata

    student_photo = factory.SubFactory(StudentPhotoFactory)
    model_name = "MobileFaceNet"
    model_version = "1.0"
    embedding = factory.LazyFunction(lambda: [0.1] * 128)  # Default embedding
    is_primary = True
    quality_score = 0.90
    captured_at = factory.LazyFunction(timezone.now)


class FaceEnrollmentFactory(DjangoModelFactory):
    """
    Factory for creating test face enrollment submissions

    Usage:
        # Create pending enrollment
        enrollment = FaceEnrollmentFactory()

        # Create approved enrollment
        enrollment = FaceEnrollmentFactory(status="approved")

        # Create with specific parent-student relationship
        parent = ParentFactory()
        student = StudentFactory()
        enrollment = FaceEnrollmentFactory(parent=parent, student=student)
    """

    class Meta:
        model = FaceEnrollment

    student = factory.SubFactory(StudentFactory)
    parent = factory.SubFactory(ParentFactory)
    status = "pending_approval"
    photo_count = 3

    @factory.lazy_attribute
    def photos_data(self):
        """Generate fake base64 photo data"""
        import base64

        # Create minimal valid base64 data (fake JPEG header)
        fake_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100
        base64_data = base64.b64encode(fake_jpeg).decode()
        return [{"data": base64_data, "content_type": "image/jpeg"} for _ in range(3)]

    device_info = factory.Dict(
        {
            "app_version": "1.0.0",
            "platform": "android",
            "platform_version": "14",
        }
    )

    submitted_at = factory.LazyFunction(timezone.now)


class FCMTokenFactory(DjangoModelFactory):
    """
    Factory for creating FCM tokens for push notifications

    Usage:
        # Create token for existing parent
        token = FCMTokenFactory(parent=parent)

        # Create with specific token string
        token = FCMTokenFactory(token="custom_fcm_token_123")
    """

    class Meta:
        model = FCMToken

    parent = factory.SubFactory(ParentFactory)
    token = factory.Sequence(lambda n: f"fcm_test_token_{n}")
    platform = "android"  # Model uses platform, not device_type
    is_active = True


class NotificationFactory(DjangoModelFactory):
    """
    Factory for creating test notifications

    Usage:
        # Create pending notification
        notification = NotificationFactory()

        # Create sent notification
        notification = NotificationFactory(status="sent")

        # Create for specific parent
        notification = NotificationFactory(parent=parent)
    """

    class Meta:
        model = Notification

    parent = factory.SubFactory(ParentFactory)
    student = factory.SubFactory(StudentFactory)
    notification_type = "boarding"
    title = factory.Sequence(lambda n: f"Test Notification {n}")
    body = "Your child boarded the bus"
    data = {"event_type": "boarding"}  # Simple default
    status = "pending"
    retry_count = 0
    error_message = ""
    created_at = factory.LazyFunction(timezone.now)


class NotificationPreferenceFactory(DjangoModelFactory):
    """
    Factory for creating notification preferences

    Usage:
        # Create default preferences
        prefs = NotificationPreferenceFactory(parent=parent)

        # Create with quiet hours enabled
        prefs = NotificationPreferenceFactory(
            parent=parent,
            quiet_hours_enabled=True
        )
    """

    class Meta:
        model = NotificationPreference

    parent = factory.SubFactory(ParentFactory)
    boarding = True
    deboarding = True
    eta = True
    pickup_reminder = True
    drop_reminder = True
    announcements = True
    quiet_hours_enabled = False
