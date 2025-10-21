"""Signal handlers for publishing real-time updates."""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver

from kiosks.models import BusLocation


@receiver(post_save, sender=BusLocation)
def publish_bus_location_update(sender, instance, created, **kwargs):
    """
    Publish bus location update to WebSocket channel when GPS ping arrives.

    Triggered by: New BusLocation record saved
    Publishes to: 'bus_updates' channel
    Consumed by: BusTrackingConsumer (school dashboard, parent app, etc.)
    """
    if not created:
        return  # Only process new locations

    kiosk = instance.kiosk
    if not kiosk or not kiosk.bus:
        return  # Kiosk not assigned to bus

    bus = kiosk.bus

    # Get channel layer
    channel_layer = get_channel_layer()
    if not channel_layer:
        return  # Channel layer not configured

    # Prepare event data
    event_data = {
        "type": "bus_location_update",
        "bus_id": str(bus.bus_id),
        "license_plate": bus.license_plate,
        "latitude": instance.latitude,
        "longitude": instance.longitude,
        "speed": instance.speed or 0,
        "heading": instance.heading or 0,
        "timestamp": instance.timestamp.isoformat(),
    }

    # Publish to channel (group send)
    async_to_sync(channel_layer.group_send)("bus_updates", event_data)
