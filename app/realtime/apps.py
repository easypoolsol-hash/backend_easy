"""Realtime app configuration."""

from django.apps import AppConfig


class RealtimeConfig(AppConfig):
    """Configuration for realtime WebSocket app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "realtime"
    verbose_name = "Real-time Communication"

    def ready(self):
        """Import signal handlers when app is ready."""
        # Import signals to register handlers
        import realtime.signals  # noqa: F401
