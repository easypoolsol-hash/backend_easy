"""
Test Bus Location Service - Firebase + PostgreSQL dual storage
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from django.utils import timezone

from buses.services.location_service import BusLocationService
from buses.models import Bus, BusLocation


@pytest.mark.django_db
class TestBusLocationService:
    """Test bus location dual storage strategy"""

    @patch('buses.services.location_service.db.reference')
    def test_update_location_writes_to_firebase(self, mock_db_ref):
        """Location update writes to Firebase Realtime DB"""
        # Setup
        bus = Bus.objects.create(
            bus_id='BUS001',
            license_plate='TEST-123',
            capacity=40
        )

        mock_firebase_ref = Mock()
        mock_db_ref.return_value = mock_firebase_ref

        # Execute
        BusLocationService.update_location(
            bus_id='BUS001',
            latitude=12.9716,
            longitude=77.5946,
            speed=45.5,
            heading=180
        )

        # Verify Firebase write
        mock_db_ref.assert_called_once_with('buses/BUS001/location')
        mock_firebase_ref.set.assert_called_once()

        call_args = mock_firebase_ref.set.call_args[0][0]
        assert call_args['lat'] == 12.9716
        assert call_args['lng'] == 77.5946
        assert call_args['speed'] == 45.5
        assert call_args['heading'] == 180

    @patch('buses.services.location_service.db.reference')
    def test_update_location_writes_to_postgresql(self, mock_db_ref):
        """Location update writes to PostgreSQL for history"""
        # Setup
        bus = Bus.objects.create(
            bus_id='BUS002',
            license_plate='TEST-456',
            capacity=50
        )

        # Execute
        BusLocationService.update_location(
            bus_id='BUS002',
            latitude=12.9716,
            longitude=77.5946,
            speed=30.0,
            heading=90
        )

        # Verify PostgreSQL write
        locations = BusLocation.objects.filter(bus=bus)
        assert locations.count() == 1

        location = locations.first()
        assert location.latitude == 12.9716
        assert location.longitude == 77.5946
        assert location.speed == 30.0
        assert location.heading == 90

    @patch('buses.services.location_service.db.reference')
    def test_get_location_history_from_postgresql(self, mock_db_ref):
        """Location history retrieved from PostgreSQL"""
        # Setup
        bus = Bus.objects.create(
            bus_id='BUS003',
            license_plate='TEST-789',
            capacity=45
        )

        # Create location history
        now = timezone.now()
        for i in range(5):
            BusLocation.objects.create(
                bus=bus,
                latitude=12.97 + (i * 0.001),
                longitude=77.59 + (i * 0.001),
                speed=40.0,
                heading=0,
                timestamp=now - timedelta(minutes=i)
            )

        # Execute
        start_time = now - timedelta(hours=1)
        end_time = now
        history = BusLocationService.get_location_history(
            'BUS003',
            start_time,
            end_time
        )

        # Verify
        assert history.count() == 5
        assert list(history) == list(history.order_by('timestamp'))

    @patch('buses.services.location_service.db.reference')
    def test_firebase_cleanup_removes_old_data(self, mock_db_ref):
        """Old Firebase data is cleaned up automatically"""
        # Setup
        bus = Bus.objects.create(
            bus_id='BUS004',
            license_plate='TEST-101',
            capacity=40
        )

        mock_history_ref = Mock()
        mock_firebase_ref = Mock()
        mock_db_ref.side_effect = [mock_firebase_ref, mock_history_ref]

        # Mock old data
        old_data = {'key1': {}, 'key2': {}}
        mock_query = Mock()
        mock_query.get.return_value = old_data
        mock_history_ref.order_by_child.return_value.end_at.return_value = mock_query

        # Execute
        BusLocationService.update_location(
            bus_id='BUS004',
            latitude=12.9716,
            longitude=77.5946
        )

        # Verify cleanup called
        mock_history_ref.order_by_child.assert_called_with('timestamp')

    @patch('buses.services.location_service.db.reference')
    def test_handles_missing_bus(self, mock_db_ref):
        """Raises error for non-existent bus"""
        with pytest.raises(Bus.DoesNotExist):
            BusLocationService.update_location(
                bus_id='NONEXISTENT',
                latitude=12.9716,
                longitude=77.5946
            )

    @patch('buses.services.location_service.db.reference')
    def test_includes_optional_fields(self, mock_db_ref):
        """Optional fields (altitude, accuracy) stored in PostgreSQL"""
        # Setup
        bus = Bus.objects.create(
            bus_id='BUS005',
            license_plate='TEST-202',
            capacity=40
        )

        # Execute
        BusLocationService.update_location(
            bus_id='BUS005',
            latitude=12.9716,
            longitude=77.5946,
            speed=35.0,
            heading=270,
            altitude=900.5,
            accuracy=5.2
        )

        # Verify
        location = BusLocation.objects.get(bus=bus)
        assert location.altitude == 900.5
        assert location.accuracy == 5.2

    @patch('buses.services.location_service.db.reference')
    def test_get_current_locations_from_firebase(self, mock_db_ref):
        """Get all current bus locations from Firebase"""
        mock_buses_ref = Mock()
        mock_buses_ref.get.return_value = {
            'BUS001': {'location': {'lat': 12.97, 'lng': 77.59}},
            'BUS002': {'location': {'lat': 12.98, 'lng': 77.60}}
        }
        mock_db_ref.return_value = mock_buses_ref

        # Execute
        locations = BusLocationService.get_current_locations()

        # Verify
        assert 'BUS001' in locations
        assert 'BUS002' in locations
        mock_db_ref.assert_called_once_with('buses')
