from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DeviceLogViewSet,
    KioskViewSet,
    activate_kiosk_view,
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
    # Specific endpoints before router
    path("kiosks/activate/", activate_kiosk_view, name="kiosk-activate"),
    # Group per-kiosk endpoints under the kiosks/ prefix so that
    # URLs like /api/v1/kiosks/<kiosk_id>/check-updates/ resolve
    path(
        "kiosks/",
        include(
            [
                path("logs/", kiosk_log, name="kiosk-logs"),
                path(
                    "<str:kiosk_id>/check-updates/",
                    check_updates,
                    name="kiosk-check-updates",
                ),
                path(
                    "<str:kiosk_id>/snapshot/",
                    download_snapshot,
                    name="kiosk-snapshot",
                ),
                path(
                    "<str:kiosk_id>/heartbeat/",
                    heartbeat,
                    name="kiosk-heartbeat-sync",
                ),
                path(
                    "<str:kiosk_id>/location/",
                    update_location,
                    name="kiosk-location",
                ),
                # Router commented out for testing
                # path("", include(router.urls)),
            ]
        ),
    ),
]
