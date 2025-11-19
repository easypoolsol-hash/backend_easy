import os

# Ensure DJANGO_SETTINGS_MODULE is defined before importing Django/DRF modules.
# Some libraries (notably DRF) read Django settings at import time which will
# raise ImproperlyConfigured unless the environment variable is present and
# django.setup() has been called.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bus_kiosk_backend.settings")
os.environ.setdefault("DJANGO_ENV", "ci")  # Use CI settings for tests

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
    """Creates an active kiosk for testing."""
    # Import factories lazily to avoid importing Django models at collection time
    from tests.factories import KioskFactory

    kiosk = KioskFactory(is_active=True)
    return kiosk


@pytest.fixture
def school_admin_user(db):
    """Creates a school admin user for testing."""
    from django.contrib.auth.models import Group

    from tests.factories import UserFactory

    user = UserFactory()
    school_admin_group, _ = Group.objects.get_or_create(name="School Administrator")
    user.groups.clear()  # Remove default group
    user.groups.add(school_admin_group)
    return user


@pytest.fixture
def parent_user(db):
    """Creates a parent user for testing."""
    from django.contrib.auth.models import Group

    from tests.factories import UserFactory

    user = UserFactory()
    parent_group, _ = Group.objects.get_or_create(name="Parent")
    user.groups.clear()  # Remove default group
    user.groups.add(parent_group)
    return user


@pytest.fixture
def approved_parent_client(db):
    """
    Creates an approved parent user with APIClient for testing parent-only endpoints.

    Returns tuple: (client, user, parent)
    - client: Authenticated APIClient
    - user: User in Parent group
    - parent: Approved Parent profile linked to user
    """
    from django.contrib.auth.models import Group

    from tests.factories import ParentFactory, UserFactory

    # Create user in Parent group
    user = UserFactory()
    parent_group, _ = Group.objects.get_or_create(name="Parent")
    user.groups.clear()
    user.groups.add(parent_group)

    # Get the auto-created Parent (from post_save signal) and update it
    from students.models import Parent
    parent = Parent.objects.get(user=user)
    parent.approval_status = "approved"
    parent.save()

    # Create authenticated client
    client = APIClient()
    client.force_authenticate(user=user)

    return client, user, parent


@pytest.fixture
def unapproved_parent_client(db):
    """
    Creates a pending parent user for testing permission denial.

    Returns tuple: (client, user, parent)
    """
    from django.contrib.auth.models import Group

    from tests.factories import ParentFactory, UserFactory

    user = UserFactory()
    parent_group, _ = Group.objects.get_or_create(name="Parent")
    user.groups.clear()
    user.groups.add(parent_group)

    # Get the auto-created Parent (from post_save signal) and update it
    from students.models import Parent
    parent = Parent.objects.get(user=user)
    parent.approval_status = "pending"
    parent.save()

    client = APIClient()
    client.force_authenticate(user=user)

    return client, user, parent


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
