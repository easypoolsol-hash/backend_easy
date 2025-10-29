"""Signal handlers for publishing real-time updates."""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from events.models import BoardingEvent
from kiosks.models import BusLocation


@receiver(post_save, sender=BoardingEvent)
def publish_boarding_event(sender, instance, created, **kwargs):
    """
    Publish boarding event to WebSocket channel when student boards.

    Triggered by: New BoardingEvent saved
    Publishes to: 'dashboard_updates' channel via Redis pub/sub
    Consumed by: DashboardConsumer (school admin dashboard)

    This is the Fortune 500 pattern:
    - Redis acts as message broker
    - ALL Django servers subscribe to Redis
    - Each server broadcasts to its WebSocket clients
    - Scales horizontally with no single point of failure
    """
    if not created:
        return  # Only process new events

    # Skip WebSocket notifications during data seeding (performance optimization)
    # Seed scripts create hundreds of events - no need for real-time notifications
    import sys

    if "seed" in " ".join(sys.argv):
        return  # Skip WebSocket during seeding

    channel_layer = get_channel_layer()
    if not channel_layer:
        return  # Channel layer not configured

    # Get student details
    student = instance.student
    if not student:
        return

    # Prepare event data for WebSocket
    event_data = {
        "type": "boarding_event",  # Handler method name in consumer
        "event_id": str(instance.event_id),
        "student_id": student.school_student_id,
        "student_name": student.encrypted_name,  # Frontend decrypts if needed
        "grade": student.grade,
        "timestamp": instance.timestamp.isoformat(),
        "kiosk_id": instance.kiosk_id,
        "event_type": instance.metadata.get("event_type", "boarding"),
    }

    # Publish to channel layer (all servers will receive this)
    try:
        async_to_sync(channel_layer.group_send)("dashboard_updates", event_data)
    except Exception as e:
        # Channel layer not available or connection failed
        # This is OK - event is still saved in database
        # WebSocket notifications are best-effort, not critical
        print(f"[WARN] Failed to publish boarding event to WebSocket: {e}")
        return

    # Update cached stats and broadcast
    today = timezone.now().date()
    cache_key_stats = f"dashboard_stats_{today}"
    try:
        cache.delete(cache_key_stats)  # Invalidate cache
    except Exception:
        pass  # Cache not available, continue

    # Calculate fresh stats
    students_boarded = BoardingEvent.objects.filter(timestamp__date=today).values("student").distinct().count()
    total_events = BoardingEvent.objects.filter(timestamp__date=today).count()

    # Broadcast updated stats
    stats_data = {
        "type": "dashboard_stats",  # Handler method name in consumer
        "students_boarded_today": students_boarded,
        "total_events_today": total_events,
    }
    try:
        async_to_sync(channel_layer.group_send)("dashboard_updates", stats_data)
    except Exception as e:
        # Channel layer error - stats update is best-effort
        print(f"[WARN] Failed to publish stats to WebSocket: {e}")


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
        "status": bus.status,  # CRITICAL: Required by frontend WebSocket consumer
        "timestamp": instance.timestamp.isoformat(),
    }

    # Publish to channel (group send)
    try:
        async_to_sync(channel_layer.group_send)("bus_updates", event_data)
    except Exception as e:
        # Channel layer not available - this is OK for local development
        print(f"[WARN] Failed to publish bus location to WebSocket: {e}")
