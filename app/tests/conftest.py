import pytest
from rest_framework.test import APIClient
import schemathesis


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
