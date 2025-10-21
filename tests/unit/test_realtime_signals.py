from unittest.mock import AsyncMock, patch

from django.utils import timezone
import pytest

from buses.models import Bus, Route
from kiosks.models import BusLocation, Kiosk


@pytest.mark.django_db
class TestBusLocationSignal:
    """Test bus location update signal handler."""

    @pytest.fixture
    def setup_bus(self):
        """Create test bus and kiosk."""
        route = Route.objects.create(
            name="Test Route",
            stops=[{"name": "Stop 1", "lat": 22.5726, "lon": 88.3639, "sequence": 1}],
            schedule={"morning": {"start": "07:00", "end": "09:00"}},
        )

        bus = Bus.objects.create(license_plate="TEST123", route=route, capacity=40, status="active")

        kiosk = Kiosk.objects.create(kiosk_id="KIOSK_TEST", bus=bus, is_active=True)

        return {"bus": bus, "kiosk": kiosk, "route": route}

    @patch("realtime.signals.get_channel_layer")
    def test_signal_publishes_new_location(self, mock_get_channel_layer, setup_bus):
        """Test that signal publishes when new location is created."""
        # Setup mock channel layer
        mock_channel_layer = AsyncMock()
        mock_get_channel_layer.return_value = mock_channel_layer

        kiosk = setup_bus["kiosk"]
        bus = setup_bus["bus"]

        # Create new location (triggers signal)
        BusLocation.objects.create(kiosk=kiosk, latitude=22.5726, longitude=88.3639, speed=35.0, heading=180.0, timestamp=timezone.now())

        # Verify channel layer group_send was called
        mock_channel_layer.group_send.assert_awaited_once()

        # Verify call arguments
        call_args = mock_channel_layer.group_send.call_args
        assert call_args[0][0] == "bus_updates"  # Channel name

        event_data = call_args[0][1]
        assert event_data["type"] == "bus_location_update"
        assert event_data["bus_id"] == str(bus.bus_id)
        assert event_data["license_plate"] == "TEST123"
        assert event_data["latitude"] == 22.5726
        assert event_data["longitude"] == 88.3639
        assert event_data["speed"] == 35.0
        assert event_data["heading"] == 180.0

    @patch("realtime.signals.get_channel_layer")
    def test_signal_ignores_updates(self, mock_get_channel_layer, setup_bus):
        """Test that signal ignores location updates (only new creates)."""
        mock_channel_layer = AsyncMock()
        mock_get_channel_layer.return_value = mock_channel_layer

        kiosk = setup_bus["kiosk"]

        # Create location
        location = BusLocation.objects.create(kiosk=kiosk, latitude=22.5726, longitude=88.3639, timestamp=timezone.now())

        # Reset mock
        mock_channel_layer.reset_mock()

        # Update location (should NOT trigger signal)
        location.speed = 40.0
        location.save()

        # Verify NO new call was made
        mock_channel_layer.group_send.assert_not_awaited()

    @patch("realtime.signals.get_channel_layer")
    def test_signal_ignores_unassigned_kiosk(self, mock_get_channel_layer):
        """Test that signal ignores locations from unassigned kiosks."""
        mock_channel_layer = AsyncMock()
        mock_get_channel_layer.return_value = mock_channel_layer

        # Create kiosk without bus
        kiosk = Kiosk.objects.create(kiosk_id="UNASSIGNED_KIOSK", is_active=True)

        # Create location
        BusLocation.objects.create(kiosk=kiosk, latitude=22.5726, longitude=88.3639, timestamp=timezone.now())

        # Verify NO call was made
        mock_channel_layer.group_send.assert_not_awaited()

    @patch("realtime.signals.get_channel_layer")
    def test_signal_handles_missing_channel_layer(self, mock_get_channel_layer, setup_bus):
        """Test that signal handles case when channel layer is not configured."""
        # Simulate missing channel layer
        mock_get_channel_layer.return_value = None

        kiosk = setup_bus["kiosk"]

        # Should not raise exception
        try:
            BusLocation.objects.create(kiosk=kiosk, latitude=22.5726, longitude=88.3639, timestamp=timezone.now())
        except Exception as e:
            pytest.fail(f"Signal handler raised exception: {e}")
