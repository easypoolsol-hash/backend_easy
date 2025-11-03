"""
Unit tests for Route serializers with polyline support.
"""

from decimal import Decimal

import pytest

from buses.serializers import RouteSerializer, RouteWaypointSerializer, WaypointSerializer
from tests.factories import PathAdjustmentWaypointFactory, RouteFactory, RouteWaypointFactory, WaypointFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestWaypointSerializer:
    """Test cases for WaypointSerializer"""

    def test_serialize_waypoint(self):
        """Test serializing a waypoint"""
        waypoint = WaypointFactory(latitude=Decimal("51.498800"), longitude=Decimal("-0.174900"), metadata={"type": "bus_stop", "name": "Test Stop"})

        serializer = WaypointSerializer(waypoint)
        data = serializer.data

        assert str(waypoint.waypoint_id) in str(data["waypoint_id"])
        assert float(data["latitude"]) == 51.498800
        assert float(data["longitude"]) == -0.174900
        assert data["metadata"]["type"] == "bus_stop"
        assert data["metadata"]["name"] == "Test Stop"

    def test_deserialize_waypoint(self):
        """Test deserializing waypoint data"""
        data = {"latitude": 51.498800, "longitude": -0.174900, "metadata": {"type": "bus_stop", "name": "New Stop"}}

        serializer = WaypointSerializer(data=data)
        assert serializer.is_valid()

        waypoint = serializer.save()
        assert waypoint.latitude == Decimal("51.498800")
        assert waypoint.longitude == Decimal("-0.174900")
        assert waypoint.metadata["type"] == "bus_stop"


@pytest.mark.unit
@pytest.mark.django_db
class TestRouteWaypointSerializer:
    """Test cases for RouteWaypointSerializer"""

    def test_serialize_route_waypoint(self):
        """Test serializing a route waypoint with nested data"""
        waypoint = WaypointFactory(latitude=Decimal("51.498800"), longitude=Decimal("-0.174900"), metadata={"type": "bus_stop", "name": "Stop 1"})
        route_waypoint = RouteWaypointFactory(waypoint=waypoint, sequence=1)

        serializer = RouteWaypointSerializer(route_waypoint)
        data = serializer.data

        assert data["sequence"] == 1
        assert float(data["latitude"]) == 51.498800
        assert float(data["longitude"]) == -0.174900
        assert data["metadata"]["type"] == "bus_stop"
        assert data["metadata"]["name"] == "Stop 1"


@pytest.mark.unit
@pytest.mark.django_db
class TestRouteSerializer:
    """Test cases for RouteSerializer with polyline support"""

    def test_serialize_route_with_cached_polyline(self):
        """Test serializing route with pre-cached polyline"""
        route = RouteFactory(name="Test Route", encoded_polyline="_p~iF~ps|U_ulLnnqC_mqNvxq`@")

        serializer = RouteSerializer(route)
        data = serializer.data

        assert data["name"] == "Test Route"
        assert data["encoded_polyline"] == "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
        assert data["bus_stops"] == []  # No waypoints yet

    def test_serialize_route_with_waypoints_generates_polyline(self):
        """Test that route without cached polyline generates one from waypoints"""
        route = RouteFactory(encoded_polyline="")  # No cached polyline

        # Create waypoints
        wp1 = WaypointFactory(latitude=Decimal("51.498800"), longitude=Decimal("-0.174900"), metadata={"type": "bus_stop", "name": "Stop 1"})
        wp2 = WaypointFactory(latitude=Decimal("51.502700"), longitude=Decimal("-0.152800"), metadata={"type": "bus_stop", "name": "Stop 2"})

        RouteWaypointFactory(route=route, waypoint=wp1, sequence=1)
        RouteWaypointFactory(route=route, waypoint=wp2, sequence=2)

        serializer = RouteSerializer(route)
        data = serializer.data

        # Should generate encoded polyline from waypoints
        assert data["encoded_polyline"] != ""
        assert len(data["encoded_polyline"]) > 0

        # Should include bus stops
        assert len(data["bus_stops"]) == 2
        assert data["bus_stops"][0]["metadata"]["name"] == "Stop 1"
        assert data["bus_stops"][1]["metadata"]["name"] == "Stop 2"

    def test_serialize_route_filters_path_adjustments_from_bus_stops(self):
        """Test that bus_stops field only includes bus stops, not path adjustments"""
        route = RouteFactory()

        # Bus stop
        wp1 = WaypointFactory(metadata={"type": "bus_stop", "name": "Start"})
        # Path adjustment (should be filtered out)
        wp2 = PathAdjustmentWaypointFactory()
        # Bus stop
        wp3 = WaypointFactory(metadata={"type": "bus_stop", "name": "End"})

        RouteWaypointFactory(route=route, waypoint=wp1, sequence=1)
        RouteWaypointFactory(route=route, waypoint=wp2, sequence=2)
        RouteWaypointFactory(route=route, waypoint=wp3, sequence=3)

        serializer = RouteSerializer(route)
        data = serializer.data

        # Should only include 2 bus stops, not the path adjustment
        assert len(data["bus_stops"]) == 2
        assert data["bus_stops"][0]["metadata"]["name"] == "Start"
        assert data["bus_stops"][1]["metadata"]["name"] == "End"

    def test_serialize_route_with_old_route_stops_fallback(self):
        """Test fallback to old route_stops when no waypoints exist"""
        from buses.models import BusStop, RouteStop

        route = RouteFactory()

        # Create old-style bus stops
        bus_stop = BusStop.objects.create(name="Old Stop", latitude=Decimal("51.498800"), longitude=Decimal("-0.174900"))

        RouteStop.objects.create(route=route, bus_stop=bus_stop, sequence=1, waypoints=[])

        serializer = RouteSerializer(route)
        data = serializer.data

        # Should fallback to old route_stops
        assert len(data["bus_stops"]) == 1
        assert data["bus_stops"][0]["metadata"]["name"] == "Old Stop"
        assert data["bus_stops"][0]["metadata"]["type"] == "bus_stop"

    def test_serialize_multiple_routes(self):
        """Test serializing multiple routes efficiently"""
        routes = [RouteFactory(name=f"Route {i}", encoded_polyline=f"polyline_{i}") for i in range(5)]

        serializer = RouteSerializer(routes, many=True)
        data = serializer.data

        assert len(data) == 5
        for i, route_data in enumerate(data):
            assert route_data["name"] == f"Route {i}"
            assert route_data["encoded_polyline"] == f"polyline_{i}"

    def test_route_serializer_includes_all_fields(self):
        """Test that serializer includes all expected fields"""
        route = RouteFactory()
        serializer = RouteSerializer(route)
        data = serializer.data

        expected_fields = {
            "route_id",
            "name",
            "description",
            "color_code",
            "line_pattern",
            "is_active",
            "stop_count",
            "total_students",
            "route_stops",
            "encoded_polyline",
            "bus_stops",
            "created_at",
            "updated_at",
        }

        assert set(data.keys()) == expected_fields

    def test_encoded_polyline_empty_when_no_waypoints_or_stops(self):
        """Test that encoded_polyline is empty when route has no waypoints or stops"""
        route = RouteFactory(encoded_polyline="")

        serializer = RouteSerializer(route)
        data = serializer.data

        assert data["encoded_polyline"] == ""
        assert data["bus_stops"] == []

    def test_bus_stops_include_sequence_and_coordinates(self):
        """Test that bus_stops include all necessary fields"""
        route = RouteFactory()

        waypoint = WaypointFactory(
            latitude=Decimal("51.498800"), longitude=Decimal("-0.174900"), metadata={"type": "bus_stop", "name": "Test Stop", "students_count": 15}
        )

        RouteWaypointFactory(route=route, waypoint=waypoint, sequence=1)

        serializer = RouteSerializer(route)
        data = serializer.data

        bus_stop = data["bus_stops"][0]
        assert "latitude" in bus_stop
        assert "longitude" in bus_stop
        assert "sequence" in bus_stop
        assert "metadata" in bus_stop
        assert bus_stop["sequence"] == 1
        assert bus_stop["metadata"]["students_count"] == 15
