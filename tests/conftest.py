import os

# Ensure DJANGO_SETTINGS_MODULE is defined before importing Django/DRF modules.
# Some libraries (notably DRF) read Django settings at import time which will
# raise ImproperlyConfigured unless the environment variable is present and
# django.setup() has been called.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.bus_kiosk_backend.test_settings")

from cryptography.fernet import Fernet
import django
from django.conf import settings
import pytest
import schemathesis

# Call django.setup() before importing modules that may access Django settings
# during import (for example DRF). This is intentional and must happen at
# module import time so pytest collection (which imports conftest) doesn't
# raise import-time errors. Marked with noqa where required above.
django.setup()

from rest_framework.test import APIClient  # noqa: E402


@pytest.fixture(autouse=True, scope="session")
def ensure_fernet_key():
    key = None
    # 1) environment
    key = os.environ.get("ENCRYPTION_KEY")
    # 2) settings (test_settings may provide a deterministic key)
    if not key and hasattr(settings, "ENCRYPTION_KEY"):
        key = settings.ENCRYPTION_KEY
    # 3) generate ephemeral key for local dev if still missing
    if not key:
        key = Fernet.generate_key().decode()
        os.environ["ENCRYPTION_KEY"] = key
        # also set in settings so code reading settings directly works
        try:
            settings.ENCRYPTION_KEY = key
        except Exception:
            pass
    # Validate key shape. If malformed, warn and generate an ephemeral key
    # so test runs do not hard-fail due to a bad environment value.
    try:
        Fernet(key.encode())
    except Exception as e:
        # Use pytest.warns is not appropriate here (context manager). Emit a
        # runtime warning via pytest.warns replacement: pytest.warns is a
        # context manager, so use warnings.warn so it surfaces in test output.
        import warnings

        warnings.warn(
            f"ENCRYPTION_KEY is invalid ({e}); generating an ephemeral key for tests",
            RuntimeWarning,
            stacklevel=2,
        )
        key = Fernet.generate_key().decode()
        os.environ["ENCRYPTION_KEY"] = key
        try:
            settings.ENCRYPTION_KEY = key
        except Exception:
            pass
    yield


# (django.setup() already called above)


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


@pytest.fixture
def school_admin_user(db):
    """Creates a school admin user for testing."""
    from tests.factories import RoleFactory, UserFactory

    school_admin_role = RoleFactory(name="school_admin")
    return UserFactory(role=school_admin_role)


@pytest.fixture
def parent_user(db):
    """Creates a parent user for testing."""
    from tests.factories import RoleFactory, UserFactory

    parent_role = RoleFactory(name="parent")
    return UserFactory(role=parent_role)


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
