from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DeviceLogViewSet,
    KioskViewSet,
    check_updates,
    download_snapshot,
    heartbeat,
    kiosk_auth,
    kiosk_heartbeat,
    kiosk_log,
)

# Create a router for the kiosks app
router = DefaultRouter()
router.register(r"kiosks", KioskViewSet, basename="kiosk")
router.register(r"logs", DeviceLogViewSet, basename="device-log")

# URL patterns
urlpatterns = [
    path("", include(router.urls)),
    # Authentication endpoint (public - no auth required)
    path("auth/", kiosk_auth, name="kiosk-auth"),
    # Protected endpoints for authenticated kiosk devices
    path("heartbeat/", kiosk_heartbeat, name="kiosk-heartbeat"),
    path("log/", kiosk_log, name="kiosk-log"),
    # Sync endpoints (per-kiosk)
    path("<str:kiosk_id>/check-updates/", check_updates, name="kiosk-check-updates"),
    path("<str:kiosk_id>/snapshot/", download_snapshot, name="kiosk-snapshot"),
    path("<str:kiosk_id>/heartbeat/", heartbeat, name="kiosk-heartbeat-sync"),
]
