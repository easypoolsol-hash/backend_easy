"""
Fortune 500 IAM-style Authorization Tests for Bus Locations API

Tests the zero-trust security model:
- Deny by default
- Explicit grants only
- Role-based access control
- Parent data filtering
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from buses.models import Bus
from kiosks.models import BusLocation, Kiosk
from users.models import Role

User = get_user_model()


@pytest.mark.django_db
class TestBusLocationIAM(TestCase):
    """Test IAM-style permissions for bus location endpoints"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create roles
        self.admin_role = Role.objects.create(name="school_admin", is_active=True)
        self.parent_role = Role.objects.create(name="parent", is_active=True)
        self.super_admin_role = Role.objects.create(name="super_admin", is_active=True)

        # Create users with different roles
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@school.com",
            password="test123",
            role=self.admin_role,
        )

        self.parent_user = User.objects.create_user(
            username="parent",
            email="parent@school.com",
            password="test123",
            role=self.parent_role,
        )

        self.super_admin = User.objects.create_user(
            username="superadmin",
            email="superadmin@school.com",
            password="test123",
            role=self.super_admin_role,
        )

        # Create bus and kiosk (bus_id is auto-generated UUID)
        self.bus = Bus.objects.create(
            license_plate="ABC-123",
            capacity=50,  # Required field
            status="active",
        )

        self.kiosk = Kiosk.objects.create(
            kiosk_id="KIOSK001",
            bus=self.bus,
        )

        # Create bus location with timestamp
        from django.utils import timezone

        BusLocation.objects.create(
            kiosk=self.kiosk,
            latitude=51.5074,
            longitude=-0.1278,
            speed=30.0,
            timestamp=timezone.now(),
        )

    def _get_token(self, user):
        """Helper: Generate JWT token for user"""
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)

    def test_unauthenticated_access_denied(self):
        """Test: Unauthenticated requests are denied (403)"""
        response = self.client.get("/school/api/bus-locations/")
        assert response.status_code == 403
        assert "Authentication required" in response.json()["error"]

    def test_school_admin_can_access(self):
        """Test: School admin can access all bus locations"""
        token = self._get_token(self.admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get("/school/api/bus-locations/")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) > 0

    def test_super_admin_can_access(self):
        """Test: Super admin can access all bus locations"""
        token = self._get_token(self.super_admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get("/school/api/bus-locations/")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"

    def test_parent_denied_admin_endpoint(self):
        """Test: Parent cannot access admin bus locations endpoint"""
        token = self._get_token(self.parent_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get("/school/api/bus-locations/")
        assert response.status_code == 403
        assert "Access denied" in response.json()["error"]
        assert response.json()["required_role"] == ["school_admin", "super_admin"]

    def test_parent_can_access_own_endpoint(self):
        """Test: Parent can access their filtered bus locations"""
        token = self._get_token(self.parent_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get("/api/v1/users/parent/my-buses/")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        # Features may be empty if parent has no children assigned

    def test_admin_cannot_access_parent_endpoint(self):
        """Test: Admin cannot access parent-specific endpoint (role mismatch)"""
        token = self._get_token(self.admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get("/api/v1/users/parent/my-buses/")
        assert response.status_code == 403
        assert "required_role" in response.json()
        assert response.json()["required_role"] == "parent"

    def test_geojson_format_correct(self):
        """Test: Response follows GeoJSON FeatureCollection spec"""
        token = self._get_token(self.admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get("/school/api/bus-locations/")
        data = response.json()

        # Verify GeoJSON structure
        assert data["type"] == "FeatureCollection"
        assert "features" in data
        assert isinstance(data["features"], list)

        if len(data["features"]) > 0:
            feature = data["features"][0]
            assert feature["type"] == "Feature"
            assert "geometry" in feature
            assert feature["geometry"]["type"] == "Point"
            assert "coordinates" in feature["geometry"]
            assert len(feature["geometry"]["coordinates"]) == 2  # [lon, lat]
            assert "properties" in feature
            assert "id" in feature["properties"]
            assert "name" in feature["properties"]

    def test_error_response_includes_role_info(self):
        """Test: 403 errors include helpful role information for debugging"""
        token = self._get_token(self.parent_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get("/school/api/bus-locations/")
        data = response.json()

        assert "your_role" in data
        assert data["your_role"] == "parent"
        assert "required_role" in data
