from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BusViewSet, RouteViewSet, bus_locations_api, geocode_address

# Create a router for the buses app
router = DefaultRouter()
router.register(r"routes", RouteViewSet, basename="route")
router.register(r"buses", BusViewSet, basename="bus")

# URL patterns
urlpatterns = [
    path("", include(router.urls)),
    # Bus locations API for school dashboard
    path("locations/", bus_locations_api, name="bus-locations"),
    # Geocoding helper API
    path("geocode/", geocode_address, name="geocode-address"),
]
