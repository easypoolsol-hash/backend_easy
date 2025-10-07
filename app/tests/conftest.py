"""
Shared test fixtures and configuration (Fortune 500 pattern)

This file contains pytest fixtures that are shared across all tests.
Uses Factory Boy for clean, reusable test data creation.
"""

import pytest
from rest_framework.test import APIClient

from .factories import (
    BusFactory,
    KioskFactory,
    ParentFactory,
    RoleFactory,
    RouteFactory,
    SchoolFactory,
    StudentFactory,
    StudentParentFactory,
    UserFactory,
)


@pytest.fixture
def api_client():
    """API client for testing endpoints"""
    return APIClient()


@pytest.fixture
def test_school(db):
    """Create test school using factory"""
    return SchoolFactory()


@pytest.fixture
def test_route(db):
    """Create test route using factory"""
    return RouteFactory()


@pytest.fixture
def test_bus(db):
    """Create test bus using factory"""
    return BusFactory()


@pytest.fixture
def test_kiosk(db):
    """
    Create test kiosk with activation token
    Returns: (kiosk, activation_token)
    """
    kiosk = KioskFactory()
    # Factory creates activation token and stores as _activation_token attribute
    return kiosk, kiosk._activation_token


@pytest.fixture
def test_student(db):
    """Create test student with encrypted name using factory"""
    student = StudentFactory(plaintext_name="Test Student")
    # Factory stores plaintext as _plaintext_name attribute
    return student


@pytest.fixture
def test_parent(db):
    """Create test parent with encrypted PII using factory"""
    parent = ParentFactory(
        plaintext_name="Test Parent",
        plaintext_email="test@example.com",
        plaintext_phone="+919876543210",
    )
    # Factory stores plaintext as _plaintext_* attributes
    return parent


@pytest.fixture
def test_student_parent(db):
    """Create student-parent relationship using factory"""
    return StudentParentFactory()


@pytest.fixture
def test_user(db):
    """Create test user with role using factory"""
    return UserFactory(password="testpass123")


@pytest.fixture
def test_role(db):
    """Create test role using factory"""
    return RoleFactory()


@pytest.fixture
def authenticated_client(api_client, test_user):
    """API client with authenticated user"""
    api_client.force_authenticate(user=test_user)
    return api_client
