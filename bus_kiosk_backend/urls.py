"""
URL configuration for bus_kiosk_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.apps import apps
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.utils import timezone
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .health import detailed_health_check, health_check, prometheus_metrics


def api_root(request):
    """Root API endpoint with basic information."""
    return JsonResponse({
        "name": "Bus Kiosk Backend API",
        "version": "1.0.0",
        "description": "Industrial REST API for Bus Kiosk face recognition system",
        "status": "operational",
        "timestamp": timezone.now().isoformat(),
        "docs": {
            "swagger_ui": "/docs/",
            "redoc": "/docs/redoc/",
            "openapi_schema": "/docs/schema/",
        },
        "health": "/health/",
        "auth": {
            "token_obtain": "/api/v1/auth/token/",
            "token_refresh": "/api/v1/auth/token/refresh/",
        }
    })


# Custom authenticated swagger view
class AuthenticatedSpectacularSwaggerView(SpectacularSwaggerView):
    permission_classes = [IsAuthenticated]


class AuthenticatedSpectacularRedocView(SpectacularRedocView):
    permission_classes = [IsAuthenticated]


urlpatterns = [
    # Admin URLs (only if admin app is installed)
]
if apps.is_installed('django.contrib.admin'):
    urlpatterns.append(path("admin/", admin.site.urls))

# Add other URLs
urlpatterns.extend([
    # Root API info (no auth required)
    path("", api_root, name="api_root"),
    # Health checks and monitoring (no auth required)
    path("health/", health_check, name="health_check"),
    path("health/detailed/", detailed_health_check, name="detailed_health_check"),
    path("metrics/", prometheus_metrics, name="prometheus_metrics"),
    # Protected API documentation (requires authentication)
    path("docs/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "docs/",
        AuthenticatedSpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "docs/redoc/",
        AuthenticatedSpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    path(
        "api/v1/",
        include(
            [
                path(
                    "auth/token/",
                    TokenObtainPairView.as_view(),
                    name="token_obtain_pair",
                ),
                path(
                    "auth/token/refresh/",
                    TokenRefreshView.as_view(),
                    name="token_refresh",
                ),
                path("", include("users.urls")),
                path("", include("students.urls")),
                path("", include("buses.urls")),
                path("", include("kiosks.urls")),
                path("", include("events.urls")),
            ]
        ),
    ),
])
