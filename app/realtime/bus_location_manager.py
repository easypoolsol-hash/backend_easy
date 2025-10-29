"""
Real-time bus location updates using Django Channels WebSockets.
This integrates with your existing WebSocket consumers.
"""

from datetime import datetime

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


class BusLocationManager:
    """Manager for sending real-time bus location updates via WebSockets."""

    @staticmethod
    def send_bus_location_update(bus_id: str, location_data: dict):
        """
        Send bus location update to all connected clients.

        Args:
            bus_id: UUID of the bus
            location_data: Dict containing location info
                {
                    'latitude': float,
                    'longitude': float,
                    'speed': float,
                    'heading': float,
                    'status': str,
                    'timestamp': str (ISO format)
                }
        """
        channel_layer = get_channel_layer()

        # Send to bus_updates group (for parent apps, tracking apps)
        async_to_sync(channel_layer.group_send)(
            "bus_updates",
            {
                "type": "bus_location_update",
                "bus_id": bus_id,
                "license_plate": location_data.get("license_plate", ""),
                "latitude": location_data["latitude"],
                "longitude": location_data["longitude"],
                "speed": location_data.get("speed", 0),
                "heading": location_data.get("heading", 0),
                "status": location_data.get("status", "unknown"),
                "timestamp": location_data.get("timestamp", datetime.now().isoformat()),
            },
        )

    @staticmethod
    def send_boarding_event(event_data: dict):
        """
        Send boarding event to dashboard clients.

        Args:
            event_data: Dict containing event info
                {
                    'event_id': str,
                    'student_id': str,
                    'student_name': str,
                    'grade': str,
                    'kiosk_id': str,
                    'event_type': str ('boarded' or 'alighted'),
                    'timestamp': str (ISO format)
                }
        """
        channel_layer = get_channel_layer()

        # Send to dashboard_updates group (for admin dashboard)
        async_to_sync(channel_layer.group_send)(
            "dashboard_updates",
            {
                "type": "boarding_event",
                "event_id": event_data["event_id"],
                "student_id": event_data["student_id"],
                "student_name": event_data["student_name"],
                "grade": event_data.get("grade", ""),
                "timestamp": event_data["timestamp"],
                "kiosk_id": event_data["kiosk_id"],
                "event_type": event_data["event_type"],
            },
        )

    @staticmethod
    def send_dashboard_stats(stats_data: dict):
        """
        Send dashboard statistics update.

        Args:
            stats_data: Dict containing stats
                {
                    'students_boarded_today': int,
                    'total_events_today': int,
                    'active_buses': int,
                    'total_students': int
                }
        """
        channel_layer = get_channel_layer()

        async_to_sync(channel_layer.group_send)(
            "dashboard_updates",
            {
                "type": "dashboard_stats",
                "students_boarded_today": stats_data.get("students_boarded_today", 0),
                "total_events_today": stats_data.get("total_events_today", 0),
                "active_buses": stats_data.get("active_buses", 0),
                "total_students": stats_data.get("total_students", 0),
            },
        )


# Example usage in your views or services:


def example_bus_location_update():
    """Example of how to send bus location updates."""
    # This would be called from your GPS tracking service
    BusLocationManager.send_bus_location_update(
        bus_id="550e8400-e29b-41d4-a716-446655440000",
        location_data={
            "license_plate": "DL-01-AB-1234",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "speed": 45.5,
            "heading": 90.0,
            "status": "active",
            "timestamp": datetime.now().isoformat(),
        },
    )


def example_boarding_event():
    """Example of how to send boarding events."""
    # This would be called when a student boards/alights
    BusLocationManager.send_boarding_event(
        {
            "event_id": "event-123",
            "student_id": "student-456",
            "student_name": "John Doe",
            "grade": "10th Grade",
            "kiosk_id": "kiosk-bus-001",
            "event_type": "boarded",
            "timestamp": datetime.now().isoformat(),
        }
    )


def example_dashboard_update():
    """Example of how to send dashboard stats."""
    # This would be called periodically or on demand
    BusLocationManager.send_dashboard_stats({"students_boarded_today": 145, "total_events_today": 167, "active_buses": 12, "total_students": 850})
