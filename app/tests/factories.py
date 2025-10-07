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
from django.utils import timezone

import factory
from buses.models import Bus, Route
from cryptography.fernet import Fernet
from django.conf import settings
from factory.django import DjangoModelFactory
from kiosks.models import Kiosk
from students.models import (
    FaceEmbeddingMetadata,
    Parent,
    School,
    Student,
    StudentParent,
    StudentPhoto,
)
from users.models import Role, User


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
    stops = []
    schedule = {}
    is_active = True


class BusFactory(DjangoModelFactory):
    """Factory for creating test buses"""

    class Meta:
        model = Bus

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

    @factory.post_generation
    def create_activation_token(self, create, extracted, **kwargs):
        """Create activation token for the kiosk after creation"""
        if not create:
            return

        from kiosks.models import KioskActivationToken

        raw_token, _ = KioskActivationToken.generate_for_kiosk(self)
        # Store the raw token for test access
        self._activation_token = raw_token


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

    school = factory.SubFactory(SchoolFactory)
    grade = "5"
    section = "A"
    assigned_bus = factory.SubFactory(BusFactory)
    status = "active"
    enrollment_date = date(2024, 1, 15)

    class Params:
        plaintext_name = "Test Student"

    @factory.lazy_attribute
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
        self._plaintext_name = (
            self.plaintext_name if hasattr(self, "plaintext_name") else "Test Student"
        )


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

    @factory.lazy_attribute
    def name(self):
        """Encrypt parent name"""
        fernet = Fernet(settings.ENCRYPTION_KEY.encode())
        plaintext = self.plaintext_name if hasattr(self, "plaintext_name") else "Test Parent"
        return fernet.encrypt(plaintext.encode()).decode()

    @factory.lazy_attribute
    def email(self):
        """Encrypt parent email"""
        fernet = Fernet(settings.ENCRYPTION_KEY.encode())
        plaintext = self.plaintext_email if hasattr(self, "plaintext_email") else "test@example.com"
        return fernet.encrypt(plaintext.encode()).decode()

    @factory.lazy_attribute
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
        self._plaintext_name = (
            self.plaintext_name if hasattr(self, "plaintext_name") else "Test Parent"
        )
        self._plaintext_email = (
            self.plaintext_email if hasattr(self, "plaintext_email") else "test@example.com"
        )
        self._plaintext_phone = (
            self.plaintext_phone if hasattr(self, "plaintext_phone") else "+919876543210"
        )


class StudentParentFactory(DjangoModelFactory):
    """Factory for creating student-parent relationships"""

    class Meta:
        model = StudentParent

    student = factory.SubFactory(StudentFactory)
    parent = factory.SubFactory(ParentFactory)
    relationship = "father"
    is_primary = True


class RoleFactory(DjangoModelFactory):
    """Factory for creating user roles"""

    class Meta:
        model = Role
        django_get_or_create = ("name",)

    name = "backend_engineer"
    permissions = {}
    is_active = True


class UserFactory(DjangoModelFactory):
    """Factory for creating test users"""

    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"testuser{n}")
    email = factory.Sequence(lambda n: f"user{n}@test.com")
    role = factory.SubFactory(RoleFactory)
    is_active = True

    @factory.post_generation
    def password(self, create, extracted):
        """Set password after creation"""
        if not create:
            return
        password = extracted if extracted else "testpass123"
        self.set_password(password)
        self.save()


class StudentPhotoFactory(DjangoModelFactory):
    """Factory for creating test student photos"""

    class Meta:
        model = StudentPhoto

    student = factory.SubFactory(StudentFactory)
    photo = factory.django.ImageField(color="blue")
    is_primary = True


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
