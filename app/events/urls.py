from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AttendanceRecordViewSet, BoardingEventViewSet

# Create a router for the events app
router = DefaultRouter()
router.register(r'boarding-events', BoardingEventViewSet, basename='boarding-event')
router.register(r'attendance', AttendanceRecordViewSet, basename='attendance')

# URL patterns
urlpatterns = [
    path('', include(router.urls)),
]
