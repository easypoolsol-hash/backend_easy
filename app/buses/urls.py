from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BusViewSet, RouteViewSet

# Create a router for the buses app
router = DefaultRouter()
router.register(r'routes', RouteViewSet, basename='route')
router.register(r'buses', BusViewSet, basename='bus')

# URL patterns
urlpatterns = [
    path('', include(router.urls)),
]
