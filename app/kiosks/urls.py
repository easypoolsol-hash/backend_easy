from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DeviceLogViewSet,
    KioskViewSet,
    check_updates,
    download_snapshot,
    heartbeat,
    kiosk_log,
    update_location,
)

# Create a router for the kiosks app
router = DefaultRouter()
router.register(r"kiosks", KioskViewSet, basename="kiosk")
router.register(r"logs", DeviceLogViewSet, basename="device-log")

# URL patterns
urlpatterns = [
    # Individual kiosk endpoints (flattened to avoid URLResolver issues)
    path("kiosks/logs/", kiosk_log, name="kiosk-logs"),
    path(
        "kiosks/<str:kiosk_id>/check-updates/",
        check_updates,
        name="kiosk-check-updates",
    ),
    path(
        "kiosks/<str:kiosk_id>/snapshot/",
        download_snapshot,
        name="kiosk-snapshot",
    ),
    path(
        "kiosks/<str:kiosk_id>/heartbeat/",
        heartbeat,
        name="kiosk-heartbeat-sync",
    ),
    path(
        "kiosks/<str:kiosk_id>/location/",
        update_location,
        name="kiosk-location",
    ),
    # Router for standard CRUD operations
    path("", include(router.urls)),
]
