from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api_views import DashboardStatsAPIView, DashboardStudentsAPIView
from .views import AttendanceRecordViewSet, BoardingEventViewSet

# Create a router for the events app
router = DefaultRouter()
router.register(r"boarding-events", BoardingEventViewSet, basename="boarding-event")
router.register(r"attendance", AttendanceRecordViewSet, basename="attendance")

# URL patterns
urlpatterns = [
    # Dashboard API endpoints
    path(
        "dashboard/stats/",
        DashboardStatsAPIView.as_view(),
        name="dashboard-stats",
    ),
    path(
        "dashboard/students/",
        DashboardStudentsAPIView.as_view(),
        name="dashboard-students",
    ),
    # ViewSet routes
    path("", include(router.urls)),
]
