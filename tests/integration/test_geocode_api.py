"""
Integration tests for geocode API endpoint.
"""

from unittest.mock import Mock, patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from tests.factories import SchoolFactory
from users.models import User


@pytest.fixture
def api_client():
    """Create API client"""
    return APIClient()


@pytest.fixture
def authenticated_user(db):
    """Create an authenticated user"""
    school = SchoolFactory()
    user = User.objects.create_user(username="test_user_geocode", email="test@example.com", password="testpass123")
    user.role = "school_admin"
    user.school = school
    user.save()
    return user


@pytest.mark.integration
@pytest.mark.django_db
class TestGeocodeAPI:
    """Integration tests for geocode API endpoint"""

    @patch("buses.services.googlemaps.Client")
    def test_geocode_success(self, mock_client, api_client, authenticated_user):
        """Test successful geocoding request"""
        # Mock Google Maps API
        mock_gmaps = Mock()
        mock_gmaps.geocode.return_value = [
            {
                "geometry": {"location": {"lat": 51.4988, "lng": -0.1749}},
                "formatted_address": "Imperial College London, Exhibition Rd, London SW7 2AZ, UK",
            }
        ]
        mock_client.return_value = mock_gmaps

        api_client.force_authenticate(user=authenticated_user)

        response = api_client.post("/api/v1/geocode/", {"address": "Imperial College London"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["latitude"] == 51.4988
        assert response.data["longitude"] == -0.1749
        assert "Imperial College London" in response.data["formatted_address"]

    def test_geocode_unauthenticated(self, api_client):
        """Test that geocode requires authentication"""
        response = api_client.post("/api/v1/geocode/", {"address": "Imperial College London"}, format="json")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_geocode_missing_address(self, api_client, authenticated_user):
        """Test geocode with missing address field"""
        api_client.force_authenticate(user=authenticated_user)

        response = api_client.post("/api/v1/geocode/", {}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "address" in str(response.data).lower()

    @patch("buses.services.googlemaps.Client")
    def test_geocode_address_not_found(self, mock_client, api_client, authenticated_user):
        """Test geocode with address that doesn't exist"""
        mock_gmaps = Mock()
        mock_gmaps.geocode.return_value = []  # No results
        mock_client.return_value = mock_gmaps

        api_client.force_authenticate(user=authenticated_user)

        response = api_client.post("/api/v1/geocode/", {"address": "NonexistentPlace12345"}, format="json")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in str(response.data).lower()

    @patch("buses.services.googlemaps.Client")
    def test_geocode_api_error(self, mock_client, api_client, authenticated_user):
        """Test geocode when Google API returns error"""
        mock_gmaps = Mock()
        mock_gmaps.geocode.side_effect = Exception("API quota exceeded")
        mock_client.return_value = mock_gmaps

        api_client.force_authenticate(user=authenticated_user)

        response = api_client.post("/api/v1/geocode/", {"address": "Imperial College London"}, format="json")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "error" in str(response.data).lower()

    @patch("buses.services.googlemaps.Client")
    def test_geocode_with_special_characters(self, mock_client, api_client, authenticated_user):
        """Test geocoding with special characters"""
        mock_gmaps = Mock()
        mock_gmaps.geocode.return_value = [
            {"geometry": {"location": {"lat": 48.8584, "lng": 2.2945}}, "formatted_address": "Tour Eiffel, Champ de Mars, Paris, France"}
        ]
        mock_client.return_value = mock_gmaps

        api_client.force_authenticate(user=authenticated_user)

        response = api_client.post("/api/v1/geocode/", {"address": "Champs-Élysées, Paris"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["latitude"] == 48.8584

    @patch("buses.services.googlemaps.Client")
    def test_geocode_multiple_requests(self, mock_client, api_client, authenticated_user):
        """Test multiple geocoding requests"""
        mock_gmaps = Mock()
        mock_gmaps.geocode.side_effect = [
            [{"geometry": {"location": {"lat": 51.4988, "lng": -0.1749}}, "formatted_address": "Imperial College London"}],
            [{"geometry": {"location": {"lat": 51.5074, "lng": -0.1278}}, "formatted_address": "Westminster, London"}],
        ]
        mock_client.return_value = mock_gmaps

        api_client.force_authenticate(user=authenticated_user)

        # First request
        response1 = api_client.post("/api/v1/geocode/", {"address": "Imperial College London"}, format="json")

        # Second request
        response2 = api_client.post("/api/v1/geocode/", {"address": "Westminster, London"}, format="json")

        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK
        assert response1.data["latitude"] != response2.data["latitude"]


@pytest.mark.integration
@pytest.mark.django_db
class TestRoutesAPIWithPolylines:
    """Integration tests for routes API with polyline support"""

    def test_get_routes_includes_encoded_polyline(self, api_client, authenticated_user):
        """Test that routes API includes encoded_polyline field"""
        from decimal import Decimal

        from tests.factories import RouteFactory, RouteWaypointFactory, WaypointFactory

        # Create route with waypoints
        route = RouteFactory(name="Test Route")
        wp1 = WaypointFactory(latitude=Decimal("51.498800"), longitude=Decimal("-0.174900"), metadata={"type": "bus_stop", "name": "Stop 1"})
        wp2 = WaypointFactory(latitude=Decimal("51.502700"), longitude=Decimal("-0.152800"), metadata={"type": "bus_stop", "name": "Stop 2"})

        RouteWaypointFactory(route=route, waypoint=wp1, sequence=1)
        RouteWaypointFactory(route=route, waypoint=wp2, sequence=2)

        api_client.force_authenticate(user=authenticated_user)

        response = api_client.get("/api/v1/buses/routes/")

        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data
        assert len(response.data["results"]) >= 1

        route_data = response.data["results"][0]
        assert "encoded_polyline" in route_data
        assert "bus_stops" in route_data
        assert len(route_data["bus_stops"]) == 2

    def test_get_routes_bus_stops_have_correct_structure(self, api_client, authenticated_user):
        """Test that bus_stops in routes API have correct structure"""
        from decimal import Decimal

        from tests.factories import RouteFactory, RouteWaypointFactory, WaypointFactory

        route = RouteFactory()
        waypoint = WaypointFactory(
            latitude=Decimal("51.498800"), longitude=Decimal("-0.174900"), metadata={"type": "bus_stop", "name": "Test Stop", "students_count": 15}
        )

        RouteWaypointFactory(route=route, waypoint=waypoint, sequence=1)

        api_client.force_authenticate(user=authenticated_user)

        response = api_client.get("/api/v1/buses/routes/")

        assert response.status_code == status.HTTP_200_OK

        route_data = response.data["results"][0]
        bus_stop = route_data["bus_stops"][0]

        # Check structure
        assert "latitude" in bus_stop
        assert "longitude" in bus_stop
        assert "sequence" in bus_stop
        assert "metadata" in bus_stop
        assert bus_stop["metadata"]["type"] == "bus_stop"
        assert bus_stop["metadata"]["name"] == "Test Stop"
