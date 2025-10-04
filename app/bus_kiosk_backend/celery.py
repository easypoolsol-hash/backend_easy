import os

from celery import Celery

# Set the default Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bus_kiosk_backend.settings")

app = Celery("bus_kiosk_backend")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Explicitly import tasks to ensure they're registered
try:
    import students.tasks  # noqa: F401
except ImportError:
    pass


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
