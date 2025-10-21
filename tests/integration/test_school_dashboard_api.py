"""Integration tests for school dashboard API endpoints."""

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone
import pytest

from kiosks.models import BusLocation, Kiosk
from tests.factories import BusFactory, KioskFactory, RouteFactory

User = get_user_model()


@pytest.mark.django_db
class TestSchoolDashboardAPI:
    """Test school dashboard API endpoints."""

    @pytest.fixture
    def setup_data(self, school_admin_user):
        """Set up test data using factories."""
        # Create route
        route = RouteFactory(
            name="Test Route",
            stops=[
                {
                    "name": "Stop 1",
                    "lat": 22.5726,
                    "lon": 88.3639,
                    "sequence": 1,
                },
                {
                    "name": "Stop 2",
                    "lat": 22.5826,
                    "lon": 88.3739,
                    "sequence": 2,
                },
            ],
            schedule={"morning": {"start": "07:00", "end": "09:00"}},
        )

        # Create buses
        bus1 = BusFactory(license_plate="WB01AB1234", route=route, capacity=50, status="active")
        bus2 = BusFactory(license_plate="WB02CD5678", route=route, capacity=40, status="active")

        # Create kiosks
        kiosk1 = KioskFactory(kiosk_id="KIOSK001", bus=bus1, is_active=True)
        kiosk2 = KioskFactory(kiosk_id="KIOSK002", bus=bus2, is_active=True)

        # Create bus locations
        location1 = BusLocation.objects.create(
            kiosk=kiosk1,
            latitude=22.5726,
            longitude=88.3639,
            speed=45.0,
            heading=90.0,
            timestamp=timezone.now(),
        )
        location2 = BusLocation.objects.create(
            kiosk=kiosk2,
            latitude=22.5826,
            longitude=88.3739,
            speed=30.0,
            heading=180.0,
            timestamp=timezone.now(),
        )

        return {
            "admin": school_admin_user,
            "route": route,
            "bus1": bus1,
            "bus2": bus2,
            "kiosk1": kiosk1,
            "kiosk2": kiosk2,
            "location1": location1,
            "location2": location2,
        }

    def test_bus_locations_api_returns_geojson(self, setup_data):
        """Test that bus locations API returns valid GeoJSON."""
        client = Client()
        client.force_login(setup_data["admin"])

        url = reverse("school_dashboard:bus_locations")
        response = client.get(url)

        assert response.status_code == 200
        data = response.json()

        # Verify GeoJSON structure
        assert data["type"] == "FeatureCollection"
        assert "features" in data
        assert len(data["features"]) == 2

    def test_bus_locations_api_feature_structure(self, setup_data):
        """Test that each feature has correct structure."""
        client = Client()
        client.force_login(setup_data["admin"])

        url = reverse("school_dashboard:bus_locations")
        response = client.get(url)
        data = response.json()

        feature = data["features"][0]

        # Verify feature structure
        assert feature["type"] == "Feature"
        assert "geometry" in feature
        assert "properties" in feature

        # Verify geometry
        assert feature["geometry"]["type"] == "Point"
        assert "coordinates" in feature["geometry"]
        assert len(feature["geometry"]["coordinates"]) == 2

        # Verify properties
        props = feature["properties"]
        assert "kiosk_id" in props
        assert "bus_name" in props
        assert "status" in props
        assert "last_update" in props
        assert "speed" in props
        assert "heading" in props

    def test_bus_locations_api_requires_authentication(self):
        """Test that API requires authentication."""
        client = Client()
        url = reverse("school_dashboard:bus_locations")
        response = client.get(url)

        assert response.status_code == 403
        data = response.json()
        assert "error" in data
        assert data["error"] == "Authentication required"

    def test_bus_locations_api_requires_admin_role(self, setup_data, parent_user):
        """Test that API requires school admin role."""
        # Use regular user (not admin)
        regular_user = parent_user

        client = Client()
        client.force_login(regular_user)

        url = reverse("school_dashboard:bus_locations")
        response = client.get(url)

        assert response.status_code == 403
        data = response.json()
        assert "error" in data
        assert data["error"] == "Access denied"

    def test_bus_locations_api_returns_latest_only(self, setup_data):
        """Test that API returns only latest location per bus."""
        kiosk1 = setup_data["kiosk1"]

        # Create older location (2 hours ago)
        BusLocation.objects.create(kiosk=kiosk1, latitude=22.5000, longitude=88.3000, timestamp=timezone.now() - timezone.timedelta(hours=2))

        # Create newer location (definitely in the future from all others)
        BusLocation.objects.create(kiosk=kiosk1, latitude=22.6000, longitude=88.4000, timestamp=timezone.now() + timezone.timedelta(seconds=10))

        client = Client()
        client.force_login(setup_data["admin"])

        url = reverse("school_dashboard:bus_locations")
        response = client.get(url)
        data = response.json()

        # Find the feature for this kiosk
        kiosk1_features = [f for f in data["features"] if f["properties"]["kiosk_id"] == "KIOSK001"]

        assert len(kiosk1_features) == 1
        feature = kiosk1_features[0]

        # Should have coordinates from NEW location, not old
        coords = feature["geometry"]["coordinates"]
        assert coords[0] == 88.4000  # longitude
        assert coords[1] == 22.6000  # latitude

    def test_bus_locations_api_handles_unassigned_kiosk(self, setup_data):
        """Test that API handles kiosks without assigned bus."""
        # Create kiosk without bus
        unassigned_kiosk = Kiosk.objects.create(kiosk_id="KIOSK_UNASSIGNED", is_active=True)

        BusLocation.objects.create(kiosk=unassigned_kiosk, latitude=22.5500, longitude=88.3500, timestamp=timezone.now())

        client = Client()
        client.force_login(setup_data["admin"])

        url = reverse("school_dashboard:bus_locations")
        response = client.get(url)
        data = response.json()

        # Find the unassigned kiosk feature
        unassigned_features = [f for f in data["features"] if f["properties"]["kiosk_id"] == "KIOSK_UNASSIGNED"]

        assert len(unassigned_features) == 1
        feature = unassigned_features[0]

        # Should show kiosk name, not bus name
        assert feature["properties"]["bus_name"] == "Kiosk KIOSK_UNASSIGNED"
        assert feature["properties"]["status"] == "Unassigned"

    def test_bus_locations_api_empty_when_no_locations(self, school_admin_user):
        """Test that API returns empty features when no locations exist."""
        # Use admin without any bus locations
        admin = school_admin_user

        client = Client()
        client.force_login(admin)

        url = reverse("school_dashboard:bus_locations")
        response = client.get(url)

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert data["features"] == []

    def test_http_api_is_snapshot_not_streaming(self, setup_data):
        """
        Test that HTTP API returns snapshot, not streaming updates.

        This verifies:
        1. HTTP GET returns current state at time of request
        2. Subsequent HTTP GET returns updated state
        3. HTTP is stateless (doesn't push updates)
        """
        client = Client()
        client.force_login(setup_data["admin"])
        url = reverse("school_dashboard:bus_locations")

        # First call - get initial state
        response1 = client.get(url)
        data1 = response1.json()
        assert len(data1["features"]) == 2

        # Bus moves (new location created)
        kiosk1 = setup_data["kiosk1"]
        BusLocation.objects.create(kiosk=kiosk1, latitude=22.6000, longitude=88.4000, speed=60.0, timestamp=timezone.now())

        # Second call - should get NEW state (not automatically pushed)
        response2 = client.get(url)
        data2 = response2.json()

        # Find the updated bus in response
        kiosk1_features = [f for f in data2["features"] if f["properties"]["kiosk_id"] == "KIOSK001"]

        # Should have new location (because we made new HTTP request)
        assert len(kiosk1_features) == 1
        coords = kiosk1_features[0]["geometry"]["coordinates"]
        assert coords[0] == 88.4000  # New longitude
        assert coords[1] == 22.6000  # New latitude

        # Key insight: HTTP requires new request to get update
        # (Unlike WebSocket which pushes automatically)


@pytest.mark.django_db
class TestSchoolDashboardViews:
    """Test school dashboard view access."""

    def test_dashboard_view_requires_authentication(self):
        """Test that dashboard view requires authentication."""
        client = Client()
        url = reverse("school_dashboard:dashboard")
        response = client.get(url)

        # Should redirect to login
        assert response.status_code == 302
        assert "/school/login/" in response.url

    def test_dashboard_view_requires_admin_role(self, parent_user):
        """Test that dashboard view requires school admin role."""
        # Use regular user
        regular_user = parent_user

        client = Client()
        client.force_login(regular_user)

        url = reverse("school_dashboard:dashboard")
        response = client.get(url)

        # Should be forbidden
        assert response.status_code == 403

    def test_dashboard_view_accessible_to_admin(self, school_admin_user):
        """Test that dashboard view is accessible to school admin."""
        admin = school_admin_user

        client = Client()
        client.force_login(admin)

        url = reverse("school_dashboard:dashboard")
        response = client.get(url)

        assert response.status_code == 200
        assert b"Dashboard Overview" in response.content
