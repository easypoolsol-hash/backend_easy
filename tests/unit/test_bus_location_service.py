"""
Test Bus Location Service - Firebase + PostgreSQL dual storage
"""

from datetime import timedelta
from unittest.mock import Mock, patch

from django.utils import timezone
import pytest

from buses.models import Bus
from buses.services.location_service import BusLocationService
from kiosks.models import BusLocation, Kiosk


@pytest.mark.django_db
class TestBusLocationService:
    """Test bus location dual storage strategy"""

    @patch("buses.services.location_service.db.reference")
    def test_update_location_writes_to_firebase(self, mock_db_ref):
        """Location update writes to Firebase Realtime DB"""
        # Setup
        bus = Bus.objects.create(bus_number="BUS001", license_plate="TEST-001", capacity=50)
        Kiosk.objects.create(kiosk_id="KIOSK001", bus=bus)

        mock_location_ref = Mock()
        mock_history_ref = Mock()
        mock_db_ref.side_effect = [mock_location_ref, mock_history_ref]

        # Mock cleanup data
        mock_query = Mock()
        mock_query.get.return_value = {}
        mock_history_ref.order_by_child.return_value.end_at.return_value = mock_query

        # Execute
        BusLocationService.update_location(bus_id="BUS001", latitude=12.9716, longitude=77.5946, speed=45.5, heading=180)

        # Verify Firebase write
        mock_db_ref.assert_any_call("buses/BUS001/location")
        mock_location_ref.set.assert_called_once()

        call_args = mock_location_ref.set.call_args[0][0]
        assert call_args["lat"] == 12.9716
        assert call_args["lng"] == 77.5946
        assert call_args["speed"] == 45.5
        assert call_args["heading"] == 180

    @patch("buses.services.location_service.db.reference")
    def test_update_location_writes_to_postgresql(self, mock_db_ref):
        """Location update writes to PostgreSQL for history"""
        # Setup
        bus = Bus.objects.create(bus_number="BUS002", license_plate="TEST-456", capacity=50)
        kiosk = Kiosk.objects.create(kiosk_id="KIOSK002", bus=bus)

        # Execute
        BusLocationService.update_location(bus_id="BUS002", latitude=12.9716, longitude=77.5946, speed=30.0, heading=90)

        # Verify PostgreSQL write
        locations = BusLocation.objects.filter(kiosk=kiosk)
        assert locations.count() == 1

        location = locations.first()
        assert location.latitude == 12.9716
        assert location.longitude == 77.5946
        assert location.speed == 30.0
        assert location.heading == 90

    @patch("buses.services.location_service.db.reference")
    def test_get_location_history_from_postgresql(self, mock_db_ref):
        """Location history retrieved from PostgreSQL"""
        # Setup
        bus = Bus.objects.create(bus_number="BUS003", license_plate="TEST-789", capacity=45)
        kiosk = Kiosk.objects.create(kiosk_id="KIOSK003", bus=bus)

        # Create location history
        now = timezone.now()
        for i in range(5):
            BusLocation.objects.create(
                kiosk=kiosk,
                latitude=12.97 + (i * 0.001),
                longitude=77.59 + (i * 0.001),
                speed=40.0,
                heading=0,
                timestamp=now - timedelta(minutes=i),
            )

        # Execute
        start_time = now - timedelta(hours=1)
        end_time = now
        history = BusLocationService.get_location_history("BUS003", start_time, end_time)

        # Verify
        assert history.count() == 5
        assert list(history) == list(history.order_by("timestamp"))

    @patch("buses.services.location_service.db.reference")
    def test_firebase_cleanup_removes_old_data(self, mock_db_ref):
        """Old Firebase data is cleaned up automatically"""
        # Setup
        bus = Bus.objects.create(bus_number="BUS004", license_plate="TEST-004", capacity=50)
        Kiosk.objects.create(kiosk_id="KIOSK004", bus=bus)

        mock_history_ref = Mock()
        mock_firebase_ref = Mock()
        mock_db_ref.side_effect = [mock_firebase_ref, mock_history_ref]

        # Mock old data
        old_data = {"key1": {}, "key2": {}}
        mock_query = Mock()
        mock_query.get.return_value = old_data
        mock_history_ref.order_by_child.return_value.end_at.return_value = mock_query

        # Execute
        BusLocationService.update_location(bus_id="BUS004", latitude=12.9716, longitude=77.5946)

        # Verify cleanup called
        mock_history_ref.order_by_child.assert_called_once_with("timestamp")

    @patch("buses.services.location_service.db.reference")
    def test_handles_missing_bus(self, mock_db_ref):
        """Raises error for non-existent bus"""
        with pytest.raises(Bus.DoesNotExist):
            BusLocationService.update_location(bus_id="NONEXISTENT", latitude=12.9716, longitude=77.5946)

    @patch("buses.services.location_service.db.reference")
    def test_includes_optional_fields(self, mock_db_ref):
        """Optional fields (altitude, accuracy) stored in PostgreSQL"""
        # Setup
        bus = Bus.objects.create(bus_number="BUS005", license_plate="TEST-202", capacity=40)
        kiosk = Kiosk.objects.create(kiosk_id="KIOSK005", bus=bus)

        # Execute
        BusLocationService.update_location(bus_id="BUS005", latitude=12.9716, longitude=77.5946, speed=35.0, heading=270, accuracy=5.2)

        # Verify
        location = BusLocation.objects.get(kiosk=kiosk)
        assert location.accuracy == 5.2

    @patch("buses.services.location_service.db.reference")
    def test_get_current_locations_from_firebase(self, mock_db_ref):
        """Get all current bus locations from Firebase"""
        mock_buses_ref = Mock()
        mock_buses_ref.get.return_value = {"BUS001": {"location": {"lat": 12.97, "lng": 77.59}}, "BUS002": {"location": {"lat": 12.98, "lng": 77.60}}}
        mock_db_ref.return_value = mock_buses_ref

        # Execute
        locations = BusLocationService.get_current_locations()

        # Verify
        assert "BUS001" in locations
        assert "BUS002" in locations
        mock_db_ref.assert_called_once_with("buses")
