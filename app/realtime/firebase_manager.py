"""
Firebase Realtime Database integration for bus tracking system.
Provides real-time data synchronization alongside Django WebSockets.
"""

import os

from django.conf import settings
import firebase_admin
from firebase_admin import credentials, db


class FirebaseRealtimeManager:
    """Manager for Firebase Realtime Database operations."""

    def __init__(self):
        if not firebase_admin._apps:
            # Initialize Firebase Admin SDK
            cred_path = os.path.join(settings.BASE_DIR, "firebase_keys", "service-account-key.json")
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred, {"databaseURL": "https://easypool-30af3-default-rtdb.firebaseio.com/"})
                self.db = db.reference()
            else:
                raise FileNotFoundError("Firebase service account key not found")

    def update_bus_location(self, bus_id: str, location_data: dict):
        """Update bus location in Firebase Realtime Database."""
        ref = self.db.child(f"buses/{bus_id}/location")
        ref.set(location_data)

    def update_dashboard_stats(self, stats_data: dict):
        """Update dashboard statistics in Firebase."""
        ref = self.db.child("dashboard/stats")
        ref.set(stats_data)

    def add_boarding_event(self, event_data: dict):
        """Add new boarding event to Firebase."""
        ref = self.db.child("events").push()
        ref.set(event_data)
        return ref.key

    def get_bus_locations(self):
        """Get all current bus locations."""
        ref = self.db.child("buses")
        return ref.get() or {}

    def listen_to_bus_updates(self, callback):
        """Listen for real-time bus location updates."""
        ref = self.db.child("buses")
        ref.listen(callback)


# Singleton instance
firebase_manager = None


def get_firebase_manager():
    """Get or create Firebase manager instance."""
    global firebase_manager
    if firebase_manager is None:
        try:
            firebase_manager = FirebaseRealtimeManager()
        except Exception as e:
            print(f"Failed to initialize Firebase: {e}")
            return None
    return firebase_manager
