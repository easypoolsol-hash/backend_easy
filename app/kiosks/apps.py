from django.apps import AppConfig


class KiosksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "kiosks"

    def ready(self):
        # Import signals to register them
        import kiosks.signals  # noqa: F401
