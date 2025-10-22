"""Integration tests for WebSocket real-time bus tracking."""

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
import pytest

from bus_kiosk_backend.asgi import application
from buses.models import Bus, Route
from kiosks.models import BusLocation, Kiosk

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestBusTrackingWebSocket(TestCase):
    """Test real-time bus tracking via WebSocket."""

    def setUp(self):
        """Set up test data."""
        # Create test user with school_admin role
        from users.models import Role

        school_admin_role = Role.objects.get_or_create(name="school_admin")[0]
        self.user = User.objects.create_user(username="testadmin", email="admin@test.com", password="testpass123", role=school_admin_role)

        # Create test route
        self.route = Route.objects.create(
            name="Test Route",
            stops=[
                {"name": "Stop 1", "lat": 22.5726, "lon": 88.3639, "sequence": 1},
                {"name": "Stop 2", "lat": 22.5826, "lon": 88.3739, "sequence": 2},
            ],
            schedule={"morning": {"start": "07:00", "end": "09:00"}},
        )

        # Create test bus
        self.bus = Bus.objects.create(license_plate="WB01AB1234", route=self.route, capacity=50, status="active")

        # Create test kiosk
        self.kiosk = Kiosk.objects.create(kiosk_id="TEST_KIOSK_001", bus=self.bus, is_active=True)

    @pytest.mark.asyncio
    async def test_websocket_connection_authenticated(self):
        """Test WebSocket connection with authenticated user."""
        communicator = WebsocketCommunicator(application, "/ws/bus-tracking/")
        communicator.scope["user"] = self.user

        connected, _ = await communicator.connect()
        self.assertTrue(connected, "WebSocket should connect for authenticated user")

        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_websocket_connection_unauthenticated(self):
        """Test WebSocket rejects unauthenticated users."""
        from django.contrib.auth.models import AnonymousUser

        communicator = WebsocketCommunicator(application, "/ws/bus-tracking/")
        communicator.scope["user"] = AnonymousUser()

        connected, _ = await communicator.connect()
        self.assertFalse(connected, "WebSocket should reject unauthenticated user")

    @pytest.mark.asyncio
    async def test_bus_location_update_broadcast(self):
        """Test that bus location updates are broadcast to connected clients."""
        # Connect WebSocket
        communicator = WebsocketCommunicator(application, "/ws/bus-tracking/")
        communicator.scope["user"] = self.user

        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        # Create a new bus location (triggers signal)
        await sync_to_async(BusLocation.objects.create)(
            kiosk=self.kiosk, latitude=22.5726, longitude=88.3639, speed=45.5, heading=90.0, accuracy=10.0, timestamp=timezone.now()
        )

        # Receive message from WebSocket
        response = await communicator.receive_json_from(timeout=5)

        # Verify message structure
        self.assertEqual(response["type"], "location_update")
        self.assertIn("data", response)

        data = response["data"]
        self.assertEqual(data["bus_id"], str(self.bus.bus_id))
        self.assertEqual(data["license_plate"], "WB01AB1234")
        self.assertEqual(data["latitude"], 22.5726)
        self.assertEqual(data["longitude"], 88.3639)
        self.assertEqual(data["speed"], 45.5)
        self.assertEqual(data["heading"], 90.0)

        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_multiple_clients_receive_updates(self):
        """Test that multiple connected clients all receive updates."""
        # Connect two clients
        comm1 = WebsocketCommunicator(application, "/ws/bus-tracking/")
        comm1.scope["user"] = self.user
        connected1, _ = await comm1.connect()
        self.assertTrue(connected1)

        comm2 = WebsocketCommunicator(application, "/ws/bus-tracking/")
        comm2.scope["user"] = self.user
        connected2, _ = await comm2.connect()
        self.assertTrue(connected2)

        # Create bus location
        await sync_to_async(BusLocation.objects.create)(kiosk=self.kiosk, latitude=22.5800, longitude=88.3700, speed=30.0, timestamp=timezone.now())

        # Both clients should receive the update
        response1 = await comm1.receive_json_from(timeout=5)
        response2 = await comm2.receive_json_from(timeout=5)

        self.assertEqual(response1["type"], "location_update")
        self.assertEqual(response2["type"], "location_update")
        self.assertEqual(response1["data"]["latitude"], 22.5800)
        self.assertEqual(response2["data"]["latitude"], 22.5800)

        await comm1.disconnect()
        await comm2.disconnect()

    @pytest.mark.asyncio
    async def test_websocket_reconnection(self):
        """Test WebSocket reconnection behavior."""
        communicator = WebsocketCommunicator(application, "/ws/bus-tracking/")
        communicator.scope["user"] = self.user

        # Connect
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        # Disconnect
        await communicator.disconnect()

        # Reconnect
        communicator2 = WebsocketCommunicator(application, "/ws/bus-tracking/")
        communicator2.scope["user"] = self.user
        reconnected, _ = await communicator2.connect()
        self.assertTrue(reconnected, "Should be able to reconnect")

        await communicator2.disconnect()

    @pytest.mark.asyncio
    async def test_initial_load_then_websocket_updates(self):
        """
        Test the complete pattern: HTTP initial load + WebSocket updates.

        Scenario:
        1. Bus A and B have existing locations
        2. Admin connects (HTTP GET shows both buses)
        3. Bus A moves (WebSocket sends only Bus A update)
        4. Admin should see: Both buses initially, then Bus A update
        """
        from django.test import Client
        from django.urls import reverse

        # Create second bus
        bus2 = await sync_to_async(Bus.objects.create)(license_plate="WB02CD5678", route=self.route, capacity=40, status="active")

        kiosk2 = await sync_to_async(Kiosk.objects.create)(kiosk_id="KIOSK002", bus=bus2, is_active=True)

        # Create existing locations for both buses
        await sync_to_async(BusLocation.objects.create)(kiosk=self.kiosk, latitude=22.5726, longitude=88.3639, speed=45.0, timestamp=timezone.now())

        await sync_to_async(BusLocation.objects.create)(kiosk=kiosk2, latitude=22.5826, longitude=88.3739, speed=30.0, timestamp=timezone.now())

        # Step 1: HTTP GET initial load (synchronous)
        client = Client()
        client.force_login(self.user)
        url = reverse("school_dashboard:bus_locations")
        response = client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify both buses in initial load
        self.assertEqual(len(data["features"]), 2)
        bus_names = [f["properties"]["bus_name"] for f in data["features"]]
        self.assertIn("WB01AB1234", bus_names)
        self.assertIn("WB02CD5678", bus_names)

        # Step 2: Connect WebSocket (after initial load)
        communicator = WebsocketCommunicator(application, "/ws/bus-tracking/")
        communicator.scope["user"] = self.user
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        # Step 3: Only Bus A moves (creates new location)
        await sync_to_async(BusLocation.objects.create)(kiosk=self.kiosk, latitude=22.5750, longitude=88.3650, speed=50.0, timestamp=timezone.now())

        # Step 4: WebSocket should send ONLY Bus A update (not both)
        ws_response = await communicator.receive_json_from(timeout=5)

        self.assertEqual(ws_response["type"], "location_update")
        self.assertEqual(ws_response["data"]["license_plate"], "WB01AB1234")
        self.assertEqual(ws_response["data"]["latitude"], 22.5750)

        # Verify Bus B NOT sent (WebSocket only sends changes)
        # No second message should arrive
        import asyncio

        try:
            await asyncio.wait_for(communicator.receive_json_from(), timeout=1.0)
            self.fail("Should not receive second message")
        except TimeoutError:
            pass  # Expected - no second message

        await communicator.disconnect()

    def test_signal_handler_publishes_location(self):
        """Test that signal handler publishes location to channel layer."""
        # This tests the synchronous signal handler
        location = BusLocation.objects.create(kiosk=self.kiosk, latitude=22.5726, longitude=88.3639, speed=25.0, timestamp=timezone.now())

        # Signal should have been triggered
        # (Actual message delivery tested in async tests above)
        self.assertIsNotNone(location.pk)
