"""
Unit tests for Waypoint and RouteWaypoint models using Factory Boy.
"""

from decimal import Decimal

import pytest

from buses.models import RouteWaypoint
from tests.factories import PathAdjustmentWaypointFactory, RouteFactory, RouteWaypointFactory, WaypointFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestWaypointModel:
    """Test cases for the Waypoint model"""

    def test_create_bus_stop_waypoint(self):
        """Test creating a waypoint that is a bus stop"""
        waypoint = WaypointFactory(
            latitude=Decimal("51.498800"),
            longitude=Decimal("-0.174900"),
            metadata={"type": "bus_stop", "name": "Imperial College Main Gate", "students_count": 15},
        )

        assert waypoint.waypoint_id is not None
        assert waypoint.latitude == Decimal("51.498800")
        assert waypoint.longitude == Decimal("-0.174900")
        assert waypoint.metadata["type"] == "bus_stop"
        assert waypoint.metadata["name"] == "Imperial College Main Gate"
        assert waypoint.is_bus_stop is True

    def test_create_path_adjustment_waypoint(self):
        """Test creating a waypoint for path adjustment"""
        waypoint = PathAdjustmentWaypointFactory(metadata={"type": "path_adjustment", "note": "Avoid highway, use local road"})

        assert waypoint.metadata["type"] == "path_adjustment"
        assert waypoint.is_bus_stop is False

    def test_waypoint_str_with_bus_stop(self):
        """Test string representation of bus stop waypoint"""
        waypoint = WaypointFactory(metadata={"type": "bus_stop", "name": "School Gate"})

        assert str(waypoint) == "School Gate (bus_stop)"

    def test_waypoint_str_without_name(self):
        """Test string representation of waypoint without name"""
        waypoint = PathAdjustmentWaypointFactory()

        waypoint_str = str(waypoint)
        assert "path_adjustment" in waypoint_str
        assert "Waypoint" in waypoint_str

    def test_waypoint_empty_metadata(self):
        """Test waypoint with empty metadata"""
        waypoint = WaypointFactory(metadata={})

        assert waypoint.is_bus_stop is False
        assert waypoint.metadata == {}

    def test_waypoint_coordinates_precision(self):
        """Test that coordinates are stored with correct precision"""
        waypoint = WaypointFactory(
            latitude=Decimal("51.4988001"),  # 7 decimal places
            longitude=Decimal("-0.1749009"),
        )

        waypoint.refresh_from_db()
        assert waypoint.latitude == Decimal("51.4988001")
        assert waypoint.longitude == Decimal("-0.1749009")

    def test_waypoint_factory_generates_valid_coords(self):
        """Test that factory generates valid latitude/longitude"""
        waypoint = WaypointFactory()

        assert -90 <= float(waypoint.latitude) <= 90
        assert -180 <= float(waypoint.longitude) <= 180


@pytest.mark.unit
@pytest.mark.django_db
class TestRouteWaypointModel:
    """Test cases for the RouteWaypoint model"""

    def test_create_route_waypoint(self):
        """Test creating a route waypoint junction"""
        route = RouteFactory()
        waypoint = WaypointFactory()

        route_waypoint = RouteWaypointFactory(route=route, waypoint=waypoint, sequence=1)

        assert route_waypoint.route == route
        assert route_waypoint.waypoint == waypoint
        assert route_waypoint.sequence == 1

    def test_route_waypoint_ordering(self):
        """Test that route waypoints are ordered by sequence"""
        route = RouteFactory()

        # Create waypoints in random order
        RouteWaypointFactory(route=route, sequence=2)
        RouteWaypointFactory(route=route, sequence=1)
        RouteWaypointFactory(route=route, sequence=3)

        waypoints = list(route.route_waypoints.all())
        assert len(waypoints) == 3
        assert waypoints[0].sequence == 1
        assert waypoints[1].sequence == 2
        assert waypoints[2].sequence == 3

    def test_route_waypoint_unique_sequence(self):
        """Test that route cannot have duplicate sequence numbers"""
        route = RouteFactory()
        waypoint1 = WaypointFactory()
        waypoint2 = WaypointFactory()

        RouteWaypointFactory(route=route, waypoint=waypoint1, sequence=1)

        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            RouteWaypointFactory(route=route, waypoint=waypoint2, sequence=1)

    def test_route_waypoint_str(self):
        """Test string representation of route waypoint"""
        route = RouteFactory(name="Route A")
        waypoint = WaypointFactory(metadata={"type": "bus_stop", "name": "Main Stop"})

        route_waypoint = RouteWaypointFactory(route=route, waypoint=waypoint, sequence=1)

        assert "Route A" in str(route_waypoint)
        assert "Seq 1" in str(route_waypoint)

    def test_cascade_delete_route(self):
        """Test that deleting route deletes route waypoints"""
        route_waypoint = RouteWaypointFactory()
        route = route_waypoint.route

        assert RouteWaypoint.objects.count() == 1

        route.delete()

        assert RouteWaypoint.objects.count() == 0

    def test_cascade_delete_waypoint(self):
        """Test that deleting waypoint deletes route waypoints"""
        route_waypoint = RouteWaypointFactory()
        waypoint = route_waypoint.waypoint

        assert RouteWaypoint.objects.count() == 1

        waypoint.delete()

        assert RouteWaypoint.objects.count() == 0

    def test_multiple_routes_same_waypoint(self):
        """Test that a waypoint can be part of multiple routes"""
        waypoint = WaypointFactory()
        route1 = RouteFactory()
        route2 = RouteFactory()

        RouteWaypointFactory(route=route1, waypoint=waypoint, sequence=1)
        RouteWaypointFactory(route=route2, waypoint=waypoint, sequence=1)

        assert waypoint.routes.count() == 2


@pytest.mark.unit
@pytest.mark.django_db
class TestRouteWithWaypoints:
    """Test Route model with waypoints"""

    def test_route_encoded_polyline_field(self):
        """Test that route can store encoded polyline"""
        route = RouteFactory(encoded_polyline="_p~iF~ps|U_ulLnnqC_mqNvxq`@")

        assert route.encoded_polyline == "_p~iF~ps|U_ulLnnqC_mqNvxq`@"

    def test_route_with_multiple_waypoints(self):
        """Test route with bus stops and path adjustments"""
        route = RouteFactory()

        # Bus stop
        wp1 = WaypointFactory(metadata={"type": "bus_stop", "name": "Start"})
        # Path adjustment
        wp2 = PathAdjustmentWaypointFactory()
        # Bus stop
        wp3 = WaypointFactory(metadata={"type": "bus_stop", "name": "End"})

        RouteWaypointFactory(route=route, waypoint=wp1, sequence=1)
        RouteWaypointFactory(route=route, waypoint=wp2, sequence=2)
        RouteWaypointFactory(route=route, waypoint=wp3, sequence=3)

        waypoints = route.route_waypoints.all()
        assert waypoints.count() == 3

        bus_stops = [rw for rw in waypoints if rw.waypoint.is_bus_stop]
        assert len(bus_stops) == 2

    def test_route_with_realistic_waypoint_data(self):
        """Test route with realistic London coordinates"""
        route = RouteFactory(name="London Route")

        # Imperial College London
        wp1 = WaypointFactory(
            latitude=Decimal("51.498800"),
            longitude=Decimal("-0.174900"),
            metadata={"type": "bus_stop", "name": "Imperial College", "students_count": 25},
        )
        # Hyde Park Corner
        wp2 = WaypointFactory(
            latitude=Decimal("51.502700"), longitude=Decimal("-0.152800"), metadata={"type": "bus_stop", "name": "Hyde Park Corner"}
        )

        RouteWaypointFactory(route=route, waypoint=wp1, sequence=1)
        RouteWaypointFactory(route=route, waypoint=wp2, sequence=2)

        assert route.route_waypoints.count() == 2

    def test_batch_create_waypoints(self):
        """Test creating multiple waypoints efficiently"""
        route = RouteFactory()
        waypoints = WaypointFactory.create_batch(5)

        for idx, waypoint in enumerate(waypoints, start=1):
            RouteWaypointFactory(route=route, waypoint=waypoint, sequence=idx)

        assert route.route_waypoints.count() == 5
