from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api_views import AllStudentsAPIView, DashboardStatsAPIView, DashboardStudentsAPIView
from .views import AttendanceRecordViewSet, BoardingEventViewSet, serve_boarding_confirmation_face

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
    # All registered students endpoint
    path(
        "students/all/",
        AllStudentsAPIView.as_view(),
        name="all-students",
    ),
    # Serve boarding confirmation face images
    path(
        "boarding-events/<str:event_id>/faces/<int:face_number>/",
        serve_boarding_confirmation_face,
        name="boarding-event-face",
    ),
    # ViewSet routes
    path("", include(router.urls)),
]
