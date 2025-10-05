"""
Shared test fixtures and configuration (Fortune 500 pattern)

This file contains pytest fixtures that are shared across all tests.
Fixtures are reusable test data and setup code.
"""

import hashlib
from datetime import date

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from buses.models import Bus, Route
from kiosks.models import Kiosk
from students.models import Parent, School, Student, StudentParent
from users.models import Role


@pytest.fixture
def api_client():
    """API client for testing endpoints"""
    return APIClient()


@pytest.fixture
def test_school(db):
    """Create test school"""
    return School.objects.create(name="Test School")


@pytest.fixture
def test_route(db, test_school):
    """Create test route"""
    return Route.objects.create(
        name="Test Route",
        stops=[],
        schedule={},
        is_active=True
    )


@pytest.fixture
def test_bus(db, test_route):
    """Create test bus"""
    return Bus.objects.create(
        license_plate="TEST-BUS-001",
        route=test_route,
        capacity=40,
        status="active"
    )


@pytest.fixture
def test_kiosk_credentials():
    """
    Test kiosk credentials
    Returns: (kiosk_id, plaintext_api_key, hashed_api_key)
    """
    kiosk_id = "TEST-KIOSK-001"
    api_key = "test-api-key-12345"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    return kiosk_id, api_key, api_key_hash


@pytest.fixture
def test_kiosk(db, test_bus, test_kiosk_credentials):
    """
    Create test kiosk with known credentials
    Returns: (kiosk, plaintext_api_key)
    """
    kiosk_id, api_key, api_key_hash = test_kiosk_credentials

    kiosk = Kiosk.objects.create(
        kiosk_id=kiosk_id,
        bus=test_bus,
        api_key_hash=api_key_hash,
        is_active=True
    )

    return kiosk, api_key


@pytest.fixture
def test_student(db, test_school, test_bus):
    """Create test student with encrypted name"""
    from cryptography.fernet import Fernet
    from django.conf import settings

    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    encrypted_name = fernet.encrypt("Test Student".encode()).decode()

    return Student.objects.create(
        school=test_school,
        name=encrypted_name,
        grade="5",
        enrollment_date=date(2024, 1, 15),
        assigned_bus=test_bus,
        status="active"
    )


@pytest.fixture
def test_parent(db):
    """Create test parent with encrypted PII"""
    from cryptography.fernet import Fernet
    from django.conf import settings

    fernet = Fernet(settings.ENCRYPTION_KEY.encode())

    return Parent.objects.create(
        name=fernet.encrypt("Test Parent".encode()).decode(),
        email=fernet.encrypt("test@example.com".encode()).decode(),
        phone=fernet.encrypt("+919876543210".encode()).decode()
    )


@pytest.fixture
def test_user(db):
    """Create test user with role"""
    role, _ = Role.objects.get_or_create(
        name="backend_engineer",
        defaults={"permissions": {}, "is_active": True}
    )

    User = get_user_model()
    return User.objects.create_user(
        username="testuser",
        email="test@test.com",
        password="testpass123",
        role=role
    )


@pytest.fixture
def authenticated_client(api_client, test_user):
    """API client with authenticated user"""
    api_client.force_authenticate(user=test_user)
    return api_client
