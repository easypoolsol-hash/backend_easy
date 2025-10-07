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
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import include, path
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .health import detailed_health_check, health_check, prometheus_metrics


@csrf_exempt
def auth_status(request):
    """Check authentication status for client-side polling."""
    if request.user.is_authenticated:
        return JsonResponse({"authenticated": True, "user": request.user.username})
    return JsonResponse({"authenticated": False}, status=401)


class NoThrottleSpectacularSwaggerView(SpectacularSwaggerView):
    """SpectacularSwaggerView that doesn't use throttling and requires admin session."""

    throttle_classes = []

    @method_decorator(login_required(login_url="/admin/login/"))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class NoThrottleSpectacularAPIView(SpectacularAPIView):
    """SpectacularAPIView that doesn't use throttling and requires admin session."""

    throttle_classes = []

    @method_decorator(login_required(login_url="/admin/login/"))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class NoThrottleSpectacularRedocView(SpectacularRedocView):
    """SpectacularRedocView that doesn't use throttling and requires admin session."""

    throttle_classes = []

    @method_decorator(login_required(login_url="/admin/login/"))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


def home(request):
    """Home page for schools and administrators."""
    context = {
        "title": "Bus Kiosk Management System",
        "description": "Face recognition system for school bus transportation",
        "current_time": timezone.now(),
        "features": [
            "Student face recognition boarding",
            "Real-time attendance tracking",
            "Bus route management",
            "Kiosk device monitoring",
            "Comprehensive API access",
        ],
        "links": {
            "admin": "/admin/",
            "api_docs": "/docs/",
            "health": "/health/",
            "api_root": "/",
        },
    }
    return render(request, "home.html", context)


def api_root(request):
    """Root API endpoint with basic information."""
    return JsonResponse(
        {
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
            },
        }
    )


urlpatterns = [
    # Admin URLs (only if admin app is installed)
]
if apps.is_installed("django.contrib.admin"):
    urlpatterns.append(path("admin/", admin.site.urls))

# Add other URLs
urlpatterns.extend(
    [
        # Home page for schools (root URL)
        path("", home, name="home"),  # type: ignore[list-item]
        # API info endpoint
        path("api/", api_root, name="api_root"),  # type: ignore[list-item]
        # Authentication status check (for client-side polling)
        path("auth-status/", auth_status, name="auth_status"),  # type: ignore[list-item]
        # Health checks and monitoring (no auth required)
        path("health/", health_check, name="health_check"),  # type: ignore[list-item]
        path("health/detailed/", detailed_health_check, name="detailed_health_check"),  # type: ignore[list-item]
        path("metrics/", prometheus_metrics, name="prometheus_metrics"),  # type: ignore[list-item]
        # API documentation - drf-spectacular with no throttling
        path(  # type: ignore[list-item]
            "docs/",
            NoThrottleSpectacularSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
        path("docs/schema/", NoThrottleSpectacularAPIView.as_view(), name="schema"),  # type: ignore[list-item]
        path(  # type: ignore[list-item]
            "docs/redoc/",
            NoThrottleSpectacularRedocView.as_view(url_name="schema"),
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
        # Authentication status endpoint
        path("api/auth/status/", auth_status, name="auth_status"),  # type: ignore[list-item]
    ]
)

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
