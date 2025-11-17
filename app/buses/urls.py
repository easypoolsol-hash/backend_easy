from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BusViewSet, RouteViewSet, bus_locations_api, bus_locations_history_api, geocode_address

# Create a router for the buses app
router = DefaultRouter()
router.register(r"routes", RouteViewSet, basename="route")
router.register(r"buses", BusViewSet, basename="bus")

# URL patterns
urlpatterns = [
    path("", include(router.urls)),
    # Bus locations API for school dashboard (ALL buses)
    path("locations/", bus_locations_api, name="bus-locations"),
    # Historical bus locations API for playback feature
    path("locations/history/", bus_locations_history_api, name="bus-locations-history"),
    # Note: Parent bus location APIs are in students/views.py and users/views.py
    # - /api/v1/parents/me/bus-locations/ (students.views.ParentMeViewSet.bus_locations)
    # - /api/v1/users/parent/my-buses/ (users.views.parent_bus_locations)
    # Geocoding helper API
    path("geocode/", geocode_address, name="geocode-address"),
]
