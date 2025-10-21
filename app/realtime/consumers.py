"""WebSocket consumers for real-time bus tracking."""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class BusTrackingConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time bus location updates.

    Used by:
    - School dashboard (admin monitoring)
    - Parent app (track child's bus)
    - Future: Driver app, fleet management

    Channel: "bus_updates" - receives GPS location changes
    """

    async def connect(self):
        """Handle WebSocket connection."""
        # Check authentication
        if not await self.is_authenticated():
            await self.close(code=4001)
            return

        # Join bus updates channel
        self.channel_name = "bus_updates"
        await self.channel_layer.group_add(
            self.channel_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave bus updates channel
        await self.channel_layer.group_discard(
            self.channel_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """
        Handle messages from WebSocket client.

        Currently not used - server pushes data only.
        Future: Could handle client filters (specific bus, route).
        """
        pass

    async def bus_location_update(self, event):
        """
        Receive bus location update from channel layer.
        Push to WebSocket client.

        Event format:
        {
            'type': 'bus_location_update',
            'bus_id': str,
            'license_plate': str,
            'latitude': float,
            'longitude': float,
            'speed': float,
            'heading': float,
            'status': str,
            'timestamp': str (ISO format)
        }
        """
        # Send to WebSocket client
        await self.send(text_data=json.dumps({
            'type': 'location_update',
            'data': {
                'bus_id': event['bus_id'],
                'license_plate': event['license_plate'],
                'latitude': event['latitude'],
                'longitude': event['longitude'],
                'speed': event['speed'],
                'heading': event['heading'],
                'status': event.get('status', 'unknown'),
                'timestamp': event['timestamp'],
            }
        }))

    @database_sync_to_async
    def is_authenticated(self):
        """Check if user is authenticated."""
        user = self.scope.get('user')
        if not user:
            return False
        return user.is_authenticated
