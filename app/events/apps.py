from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "events"

    def ready(self):
        """Import signal handlers when the app is ready"""
        # BigQuery real-time streaming (enabled in DEV settings)
        import analytics.signals  # noqa: F401

        import events.signals  # noqa: F401
