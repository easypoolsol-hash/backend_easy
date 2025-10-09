import os

import django
import pytest
from rest_framework.test import APIClient
import schemathesis

# Ensure Django settings module is set and apps are loaded early so that importing
# models during test collection (some tests import models at module level) does
# not raise AppRegistryNotReady.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bus_kiosk_backend.test_settings")
django.setup()


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup):
    """Ensure database is set up for all tests."""
    # pytest-django handles this automatically, but we can customize if needed
    pass


@pytest.fixture
def api_client():
    """A DRF API client for making unauthenticated requests."""
    return APIClient()


@pytest.fixture
def authenticated_client(db):
    """A DRF API client authenticated as a regular user."""
    # Import factories lazily to avoid importing Django models at collection time
    from tests.factories import UserFactory

    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def test_kiosk(db):
    """Creates an active kiosk and returns the instance and its activation token."""
    # Import factories lazily to avoid importing Django models at collection time
    from tests.factories import KioskFactory

    kiosk = KioskFactory(is_active=True)
    # The raw token is stored on the factory instance for test purposes
    return kiosk, kiosk._activation_token


# This fixture makes the OpenAPI schema available to all tests, including schemathesis.
@pytest.fixture(scope="session")
def schemathesis_schema():
    # The path is relative to the root directory where pytest is run.
    return schemathesis.from_path("openapi-schema.yaml")


@pytest.fixture(scope="session")
def openapi_helper():
    """Return a small helper to look up canonical paths from the OpenAPI schema."""
    from tests.utils.openapi_paths import get_path_by_operation

    return get_path_by_operation
