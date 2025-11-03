"""
Unit tests for LocationService and PolylineService using mocks.
"""

from unittest.mock import Mock, patch

import pytest

from buses.services import LocationService, PolylineService


@pytest.mark.unit
class TestLocationService:
    """Test cases for LocationService (geocoding)"""

    @patch("buses.services.googlemaps.Client")
    def test_geocode_address_success(self, mock_client):
        """Test successful address geocoding"""
        # Mock Google Maps API response
        mock_gmaps = Mock()
        mock_gmaps.geocode.return_value = [
            {
                "geometry": {"location": {"lat": 51.4988, "lng": -0.1749}},
                "formatted_address": "Imperial College London, Exhibition Rd, London SW7 2AZ, UK",
            }
        ]
        mock_client.return_value = mock_gmaps

        service = LocationService()
        result = service.geocode_address("Imperial College London")

        assert result["latitude"] == 51.4988
        assert result["longitude"] == -0.1749
        assert "Imperial College London" in result["formatted_address"]
        mock_gmaps.geocode.assert_called_once_with("Imperial College London")

    @patch("buses.services.googlemaps.Client")
    def test_geocode_address_not_found(self, mock_client):
        """Test geocoding with address not found"""
        mock_gmaps = Mock()
        mock_gmaps.geocode.return_value = []  # No results
        mock_client.return_value = mock_gmaps

        service = LocationService()

        with pytest.raises(ValueError, match="Location not found"):
            service.geocode_address("NonexistentPlace12345")

    @patch("buses.services.googlemaps.Client")
    def test_geocode_address_api_error(self, mock_client):
        """Test geocoding with API error"""
        mock_gmaps = Mock()
        mock_gmaps.geocode.side_effect = Exception("API quota exceeded")
        mock_client.return_value = mock_gmaps

        service = LocationService()

        with pytest.raises(ValueError, match="Geocoding failed"):
            service.geocode_address("Imperial College London")

    @patch("buses.services.googlemaps.Client")
    def test_geocode_with_special_characters(self, mock_client):
        """Test geocoding with special characters in address"""
        mock_gmaps = Mock()
        mock_gmaps.geocode.return_value = [
            {"geometry": {"location": {"lat": 48.8584, "lng": 2.2945}}, "formatted_address": "Tour Eiffel, Paris, France"}
        ]
        mock_client.return_value = mock_gmaps

        service = LocationService()
        result = service.geocode_address("Eiffel Tower, Paris, France")

        assert result["latitude"] == 48.8584
        assert result["longitude"] == 2.2945

    @patch("buses.services.settings")
    def test_missing_api_key(self, mock_settings):
        """Test that service raises error when API key is missing"""
        mock_settings.GOOGLE_MAPS_API_KEY = None

        with pytest.raises(ValueError, match="GOOGLE_MAPS_API_KEY not configured"):
            LocationService()


@pytest.mark.unit
class TestPolylineService:
    """Test cases for PolylineService"""

    @patch("buses.services.googlemaps.Client")
    def test_generate_route_polyline_success(self, mock_client):
        """Test successful polyline generation"""
        mock_gmaps = Mock()
        mock_gmaps.directions.return_value = [{"overview_polyline": {"points": "_p~iF~ps|U_ulLnnqC_mqNvxq`@"}}]
        mock_client.return_value = mock_gmaps

        service = PolylineService()
        waypoints = [
            (51.4988, -0.1749),  # Imperial College
            (51.5027, -0.1528),  # Hyde Park Corner
        ]

        result = service.generate_route_polyline(waypoints)

        assert result == "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
        mock_gmaps.directions.assert_called_once()

    @patch("buses.services.googlemaps.Client")
    def test_generate_polyline_with_intermediate_waypoints(self, mock_client):
        """Test polyline generation with intermediate waypoints"""
        mock_gmaps = Mock()
        mock_gmaps.directions.return_value = [{"overview_polyline": {"points": "encoded_polyline_string"}}]
        mock_client.return_value = mock_gmaps

        service = PolylineService()
        waypoints = [
            (51.4988, -0.1749),  # Origin
            (51.5000, -0.1600),  # Intermediate
            (51.5027, -0.1528),  # Destination
        ]

        result = service.generate_route_polyline(waypoints)

        assert result == "encoded_polyline_string"

        # Check that intermediate waypoints were passed correctly
        call_args = mock_gmaps.directions.call_args
        assert call_args[1]["origin"] == (51.4988, -0.1749)
        assert call_args[1]["destination"] == (51.5027, -0.1528)
        assert call_args[1]["waypoints"] == [(51.5000, -0.1600)]
        assert call_args[1]["optimize_waypoints"] is False

    @patch("buses.services.googlemaps.Client")
    def test_generate_polyline_insufficient_waypoints(self, mock_client):
        """Test that error is raised with insufficient waypoints"""
        service = PolylineService()

        with pytest.raises(ValueError, match="At least 2 waypoints required"):
            service.generate_route_polyline([(51.4988, -0.1749)])

    @patch("buses.services.googlemaps.Client")
    def test_generate_polyline_no_route_found(self, mock_client):
        """Test when no route is found between waypoints"""
        mock_gmaps = Mock()
        mock_gmaps.directions.return_value = []  # No route found
        mock_client.return_value = mock_gmaps

        service = PolylineService()
        waypoints = [(51.4988, -0.1749), (51.5027, -0.1528)]

        with pytest.raises(ValueError, match="No route found"):
            service.generate_route_polyline(waypoints)

    @patch("buses.services.googlemaps.Client")
    def test_generate_polyline_api_error(self, mock_client):
        """Test polyline generation with API error"""
        mock_gmaps = Mock()
        mock_gmaps.directions.side_effect = Exception("API error")
        mock_client.return_value = mock_gmaps

        service = PolylineService()
        waypoints = [(51.4988, -0.1749), (51.5027, -0.1528)]

        with pytest.raises(ValueError, match="Polyline generation failed"):
            service.generate_route_polyline(waypoints)

    @patch("buses.services.settings")
    def test_polyline_service_missing_api_key(self, mock_settings):
        """Test that PolylineService raises error when API key is missing"""
        mock_settings.GOOGLE_MAPS_API_KEY = None

        with pytest.raises(ValueError, match="GOOGLE_MAPS_API_KEY not configured"):
            PolylineService()


@pytest.mark.unit
class TestPolylineEncodingDecoding:
    """Test polyline encoding/decoding functionality"""

    def test_polyline_encoding(self):
        """Test that polyline library encodes coordinates correctly"""
        import polyline

        coords = [(51.4988, -0.1749), (51.5027, -0.1528)]

        encoded = polyline.encode(coords, 5)

        assert isinstance(encoded, str)
        assert len(encoded) > 0

    def test_polyline_decoding(self):
        """Test that polyline library decodes correctly"""
        import polyline

        encoded = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
        decoded = polyline.decode(encoded, 5)

        assert isinstance(decoded, list)
        assert len(decoded) > 0
        assert all(isinstance(coord, tuple) and len(coord) == 2 for coord in decoded)

    def test_polyline_roundtrip(self):
        """Test encoding and decoding roundtrip"""
        import polyline

        original = [(51.4988, -0.1749), (51.5027, -0.1528), (51.5055, -0.1410)]

        encoded = polyline.encode(original, 5)
        decoded = polyline.decode(encoded, 5)

        # Check that coordinates are approximately equal (within precision)
        assert len(decoded) == len(original)
        for orig, dec in zip(original, decoded, strict=False):
            assert abs(orig[0] - dec[0]) < 0.00001  # Latitude
            assert abs(orig[1] - dec[1]) < 0.00001  # Longitude
