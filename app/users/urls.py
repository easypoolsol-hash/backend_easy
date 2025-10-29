from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"groups", views.GroupViewSet)  # Django Groups (Roles) - READ ONLY per IAM principle
router.register(r"users", views.UserViewSet)
router.register(r"api-keys", views.APIKeyViewSet)
router.register(r"audit-logs", views.AuditLogViewSet)

urlpatterns = [
    path("", include(router.urls)),
    # NOTE: User authentication is handled by Firebase (no JWT login endpoint)
    # Kiosk authentication uses /api/v1/kiosks/activate/ endpoint
    # Parent-specific endpoints (IAM-filtered)
    path("parent/my-buses/", views.parent_bus_locations, name="parent_bus_locations"),
]
