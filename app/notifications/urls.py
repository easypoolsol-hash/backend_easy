from django.urls import include, path
from rest_framework.routers import DefaultRouter

from notifications.views import NotificationProcessView, ParentNotificationViewSet

router = DefaultRouter()

# Parent notification endpoints - nested under /parents/me/
router.register(r"parents/me", ParentNotificationViewSet, basename="parent-notifications")

urlpatterns = [
    # Router URLs (parent notification management)
    path("", include(router.urls)),
    # Internal endpoint for Cloud Tasks
    path("notifications/process/", NotificationProcessView.as_view(), name="notification-process"),
]
