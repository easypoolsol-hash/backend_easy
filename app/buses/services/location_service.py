"""
Bus Location Service - Smart dual storage strategy

Firebase Realtime DB: Live tracking (last 5 minutes)
PostgreSQL: Permanent history for analytics/compliance

Flow:
1. Kiosk sends GPS → Backend receives
2. Backend writes to Firebase (instant update for frontend)
3. Backend writes to PostgreSQL (permanent record)
4. Firebase auto-expires old data (keeps only 5 min)
"""

from datetime import datetime, timedelta
import logging

from django.utils import timezone
from firebase_admin import db

from buses.models import Bus
from kiosks.models import BusLocation

logger = logging.getLogger(__name__)


class BusLocationService:
    """Manages bus location updates with dual storage"""

    @staticmethod
    def update_location(bus_id: str, latitude: float, longitude: float, speed: float = 0, heading: float = 0, **kwargs):
        """
        Update bus location in both Firebase and PostgreSQL

        Args:
            bus_id: Bus identifier
            latitude: GPS latitude
            longitude: GPS longitude
            speed: Speed in km/h
            heading: Direction in degrees (0-360)
            **kwargs: altitude, accuracy, etc.
        """
        timestamp = timezone.now()

        try:
            # 1. Write to Firebase Realtime DB (live tracking)
            firebase_ref = db.reference(f"buses/{bus_id}/location")
            firebase_ref.set(
                {
                    "lat": latitude,
                    "lng": longitude,
                    "speed": speed,
                    "heading": heading,
                    "timestamp": timestamp.isoformat(),
                    "updated_at": {".sv": "timestamp"},  # Firebase server timestamp
                }
            )

            # 2. Write to PostgreSQL (permanent storage)
            bus = Bus.objects.get(bus_id=bus_id)
            kiosk = bus.kiosk
            BusLocation.objects.create(
                kiosk=kiosk,
                latitude=latitude,
                longitude=longitude,
                speed=speed,
                heading=heading,
                accuracy=kwargs.get("accuracy"),
                timestamp=timestamp,
            )

            # 3. Clean old Firebase data (keep only last 5 minutes)
            BusLocationService._cleanup_old_firebase_data(bus_id)

            logger.info(f"Updated location for bus {bus_id}: ({latitude}, {longitude})")

        except Bus.DoesNotExist:
            logger.error(f"Bus {bus_id} not found")
            raise
        except Exception as e:
            logger.error(f"Failed to update location for bus {bus_id}: {e}")
            raise

    @staticmethod
    def _cleanup_old_firebase_data(bus_id: str):
        """Remove Firebase data older than 5 minutes"""
        try:
            cutoff_time = timezone.now() - timedelta(minutes=5)
            history_ref = db.reference(f"buses/{bus_id}/history")

            # Query old data and remove
            old_data = history_ref.order_by_child("timestamp").end_at(cutoff_time.isoformat()).get()

            if old_data:
                for key in old_data.keys():
                    history_ref.child(key).delete()

        except Exception as e:
            logger.warning(f"Firebase cleanup failed for bus {bus_id}: {e}")

    @staticmethod
    def get_current_locations():
        """Get current locations for all active buses"""
        try:
            buses_ref = db.reference("buses")
            return buses_ref.get() or {}
        except Exception as e:
            logger.error(f"Failed to get current locations: {e}")
            return {}

    @staticmethod
    def get_location_history(bus_id: str, start_time: datetime, end_time: datetime):
        """
        Get location history from PostgreSQL (for analytics)

        Args:
            bus_id: Bus identifier
            start_time: Start of time range
            end_time: End of time range

        Returns:
            QuerySet of BusLocation objects
        """
        return BusLocation.objects.filter(kiosk__bus__bus_id=bus_id, timestamp__gte=start_time, timestamp__lte=end_time).order_by("timestamp")
