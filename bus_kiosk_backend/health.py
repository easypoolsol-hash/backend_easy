"""
Health check endpoints for monitoring system status.
"""

import time

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET


@require_GET
def health_check(request):
    """
    Basic health check endpoint.

    Returns system status and basic metrics.
    """
    return JsonResponse({
        "status": "healthy",
        "timestamp": time.time(),
        "service": "bus-kiosk-backend",
        "version": "1.0.0",
    })


@require_GET
def detailed_health_check(request):
    """
    Detailed health check with database and cache connectivity tests.
    """
    health_data = {
        "status": "healthy",
        "timestamp": time.time(),
        "service": "bus-kiosk-backend",
        "version": "1.0.0",
        "checks": {},
    }

    # Database check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health_data["checks"]["database"] = {"status": "healthy", "response_time": "ok"}
    except Exception as e:
        health_data["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
        health_data["status"] = "unhealthy"

    # Cache check (if Redis is available)
    try:
        from django.core.cache import cache

        cache.set("health_check", "ok", 10)
        cache_value = cache.get("health_check")
        if cache_value == "ok":
            health_data["checks"]["cache"] = {"status": "healthy"}
        else:
            health_data["checks"]["cache"] = {
                "status": "unhealthy",
                "error": "Cache not working",
            }
            health_data["status"] = "unhealthy"
    except Exception as e:
        health_data["checks"]["cache"] = {"status": "unhealthy", "error": str(e)}

    # Celery check (if available)
    try:
        from celery import current_app

        inspect = current_app.control.inspect()
        active_tasks = inspect.active()
        if active_tasks:
            health_data["checks"]["celery"] = {
                "status": "healthy",
                "active_workers": len(active_tasks),
            }
        else:
            health_data["checks"]["celery"] = {
                "status": "warning",
                "message": "No active workers",
            }
    except Exception as e:
        health_data["checks"]["celery"] = {"status": "unhealthy", "error": str(e)}

    response_status = (
        200
        if health_data["status"] == "healthy"
        else 503
    )
    return JsonResponse(health_data, status=response_status)


@require_GET
@cache_page(60)  # Cache for 1 minute
def prometheus_metrics(request):
    """
    Expose Prometheus metrics endpoint.
    """
    try:
        from django_prometheus import exports

        return exports.ExportToDjangoView(request)
    except ImportError:
        return JsonResponse({"error": "Prometheus not configured"}, status=503)
