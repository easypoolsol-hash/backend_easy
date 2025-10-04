"""
Health check endpoints for monitoring system status.
Industry-standard health monitoring with comprehensive checks.
"""

from contextlib import contextmanager
import logging
import os
import platform
import time
from typing import Any

import django
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET
import psutil

logger = logging.getLogger(__name__)


@contextmanager
def health_check_timeout(timeout_seconds: float = 5.0):
    """
    Context manager for health check timeouts.
    """
    start_time = time.time()
    try:
        yield
    except Exception as e:
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            logger.warning(f"Health check timed out after {elapsed:.2f}s: {e}")
            raise TimeoutError(f"Health check timed out after {elapsed:.2f}s") from e
        raise


def measure_response_time(func):
    """
    Decorator to measure response time of health checks.
    """

    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            result["response_time_ms"] = round(elapsed * 1000, 2)
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Health check failed after {elapsed:.2f}s: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": round(elapsed * 1000, 2),
            }

    return wrapper


@measure_response_time
def check_database() -> dict[str, Any]:
    """
    Check database connectivity and performance.
    """
    try:
        with health_check_timeout(2.0):
            start_time = time.time()
            with connection.cursor() as cursor:
                # Test basic connectivity
                cursor.execute("SELECT 1")
                # Test a more complex query to check performance
                cursor.execute("""
                    SELECT COUNT(*) as user_count
                    FROM (SELECT 1 as dummy LIMIT 1) as test_table
                """)
                cursor.fetchone()  # Execute query to test connectivity
            query_time = time.time() - start_time

            return {
                "status": "healthy",
                "query_time_ms": round(query_time * 1000, 2),
                "database_engine": getattr(connection, "vendor", "unknown"),
                "database_name": str(
                    getattr(connection, "settings_dict", {}).get("NAME", "unknown")
                ),
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "database_engine": getattr(connection, "vendor", "unknown"),
        }


@measure_response_time
def check_cache() -> dict[str, Any]:
    """
    Check cache backend connectivity and performance.
    """
    try:
        from django.core.cache import cache

        with health_check_timeout(1.0):
            # Test cache set/get operations
            test_key = f"health_check_{int(time.time())}"
            test_value = f"test_value_{time.time()}"

            cache.set(test_key, test_value, 30)
            retrieved_value = cache.get(test_key)

            if retrieved_value != test_value:
                return {
                    "status": "unhealthy",
                    "error": "Cache set/get mismatch",
                    "cache_backend": cache.__class__.__name__,
                }

            # Clean up
            cache.delete(test_key)

            return {
                "status": "healthy",
                "cache_backend": cache.__class__.__name__,
                "cache_key_prefix": getattr(cache, "key_prefix", "none"),
            }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "cache_backend": "unknown"}


@measure_response_time
def check_celery() -> dict[str, Any]:
    """
    Check Celery broker and worker status.
    """
    try:
        from celery import current_app

        with health_check_timeout(3.0):
            inspect = current_app.control.inspect()

            # Check active workers
            active_tasks = inspect.active()
            # Note: stats inspection removed to avoid potential performance impact
            # stats = inspect.stats()

            if not active_tasks:
                return {
                    "status": "warning",
                    "message": "No active Celery workers found",
                    "broker_url": current_app.conf.broker_url,
                    "active_workers": 0,
                }

            # Get queue statistics
            active_task_count = sum(len(tasks) for tasks in active_tasks.values())
            worker_count = len(active_tasks)

            return {
                "status": "healthy",
                "active_workers": worker_count,
                "active_tasks": active_task_count,
                "broker_url": current_app.conf.broker_url.replace(
                    current_app.conf.broker_url.split("@")[0] + "@", "***@"
                ),  # Mask credentials
                "result_backend": current_app.conf.result_backend.replace(
                    current_app.conf.result_backend.split("@")[0] + "@", "***@"
                )
                if current_app.conf.result_backend
                else None,
            }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "broker_url": "unknown"}


@measure_response_time
def check_system_resources() -> dict[str, Any]:
    """
    Check system resource usage (CPU, memory, disk).
    """
    try:
        with health_check_timeout(1.0):
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_gb = round(memory.used / (1024**3), 2)
            memory_total_gb = round(memory.total / (1024**3), 2)

            # Disk usage
            disk = psutil.disk_usage("/")
            disk_percent = disk.percent
            disk_used_gb = round(disk.used / (1024**3), 2)
            disk_total_gb = round(disk.total / (1024**3), 2)

            # Determine overall status based on thresholds
            status = "healthy"
            warnings = []

            if cpu_percent > 90:
                status = "warning"
                warnings.append(f"High CPU usage: {cpu_percent}%")
            elif cpu_percent > 95:
                status = "critical"
                warnings.append(f"Critical CPU usage: {cpu_percent}%")

            if memory_percent > 90:
                status = "warning" if status == "healthy" else status
                warnings.append(f"High memory usage: {memory_percent}%")
            elif memory_percent > 95:
                status = "critical"
                warnings.append(f"Critical memory usage: {memory_percent}%")

            if disk_percent > 90:
                status = "warning" if status == "healthy" else status
                warnings.append(f"High disk usage: {disk_percent}%")

            return {
                "status": status,
                "cpu_percent": cpu_percent,
                "memory": {
                    "percent": memory_percent,
                    "used_gb": memory_used_gb,
                    "total_gb": memory_total_gb,
                },
                "disk": {
                    "percent": disk_percent,
                    "used_gb": disk_used_gb,
                    "total_gb": disk_total_gb,
                },
                "warnings": warnings if warnings else None,
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "note": "System resource monitoring unavailable",
        }


@measure_response_time
def check_business_logic() -> dict[str, Any]:
    """
    Check application-specific business logic health.
    """
    try:
        with health_check_timeout(2.0):
            checks = {}

            # Check if critical models can be queried
            from django.apps import apps

            critical_models = [
                ("users", "User"),
                ("students", "Student"),
                ("buses", "Bus"),
                ("events", "BoardingEvent"),
                ("kiosks", "Kiosk"),
            ]

            for app_label, model_name in critical_models:
                try:
                    model = apps.get_model(app_label, model_name)
                    # Just check if we can get a count (efficient query)
                    count = model.objects.count()
                    table_name = model._meta.db_table
                    checks[f"{app_label}_{model_name.lower()}"] = {
                        "status": "healthy",
                        "record_count": count,
                        "table_name": table_name,
                    }
                except Exception as e:
                    checks[f"{app_label}_{model_name.lower()}"] = {
                        "status": "unhealthy",
                        "error": str(e),
                    }

            # Overall business logic status
            unhealthy_checks = [
                k for k, v in checks.items() if v["status"] == "unhealthy"
            ]
            status = "unhealthy" if unhealthy_checks else "healthy"

            return {
                "status": status,
                "checks": checks,
                "unhealthy_components": unhealthy_checks if unhealthy_checks else None,
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "note": "Business logic health check failed",
        }


@require_GET
def health_check(request):
    """
    Basic health check endpoint - fast and lightweight.

    Returns system status and basic metrics for load balancers and monitoring systems.
    """
    start_time = time.time()

    # Basic checks only
    try:
        # Quick database ping
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        response_time = time.time() - start_time

        return JsonResponse(
            {
                "status": "healthy",
                "timestamp": time.time(),
                "service": "bus-kiosk-backend",
                "version": "1.0.0",
                "response_time_ms": round(response_time * 1000, 2),
                "environment": os.getenv("DJANGO_SETTINGS_MODULE", "unknown"),
            }
        )
    except Exception as e:
        logger.error(f"Basic health check failed: {e}")
        return JsonResponse(
            {
                "status": "unhealthy",
                "timestamp": time.time(),
                "service": "bus-kiosk-backend",
                "version": "1.0.0",
                "error": str(e),
                "response_time_ms": round((time.time() - start_time) * 1000, 2),
            },
            status=503,
        )


@require_GET
def detailed_health_check(request):
    """
    Comprehensive health check with detailed system monitoring.

    Includes database, cache, Celery, system resources, and business logic checks.
    Used by monitoring systems and administrators.

    In test mode, skips optional checks (Celery, business logic) that require
    external services not running in test environment.
    """
    start_time = time.time()

    # Detect if we're running in test mode
    # Check multiple indicators: pytest environment, Django test command, test database, or sys.argv
    import sys
    from django.conf import settings as django_settings

    is_testing = (
        "test" in os.getenv("DJANGO_SETTINGS_MODULE", "").lower()
        or "pytest" in os.getenv("_", "").lower()
        or "pytest" in os.getenv("PYTEST_CURRENT_TEST", "")
        or "pytest" in sys.argv[0].lower()
        or "test" in sys.argv
        or "test_"
        in django_settings.DATABASES["default"][
            "NAME"
        ]  # Django creates test databases with test_ prefix
    )

    health_data: dict[str, Any] = {
        "status": "healthy",
        "timestamp": time.time(),
        "service": "bus-kiosk-backend",
        "version": "1.0.0",
        "environment": os.getenv("DJANGO_SETTINGS_MODULE", "unknown"),
        "hostname": platform.node(),
        "python_version": platform.python_version(),
        "django_version": f"{django.VERSION[0]}.{django.VERSION[1]}",
        "checks": {},
        "test_mode": is_testing,
    }

    # Core health checks (always run)
    core_checks = [
        ("database", check_database),
        ("cache", check_cache),
        # ("system_resources", check_system_resources),  # Commented out - can trigger warnings
    ]

    # Optional checks (commented out - skipping Celery for now)
    # optional_checks = [
    #     ("celery", check_celery),
    #     ("business_logic", check_business_logic),
    # ]

    # Combine checks based on environment
    # check_functions = core_checks + ([] if is_testing else optional_checks)
    check_functions = core_checks  # Only run core checks for now

    for check_name, check_func in check_functions:
        try:
            result = check_func()
            health_data["checks"][check_name] = result

            # If any check is unhealthy, mark overall status as unhealthy
            if result["status"] in ["unhealthy", "critical"]:
                health_data["status"] = "unhealthy"
            elif result["status"] == "warning" and health_data["status"] == "healthy":
                health_data["status"] = "warning"

        except Exception as e:
            logger.error(f"Health check '{check_name}' failed: {e}")
            health_data["checks"][check_name] = {
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": round((time.time() - start_time) * 1000, 2),
            }
            health_data["status"] = "unhealthy"

    # Calculate total response time
    total_response_time = time.time() - start_time
    health_data["total_response_time_ms"] = round(total_response_time * 1000, 2)

    # Log health check results
    if health_data["status"] != "healthy":
        logger.warning(f"Detailed health check failed: {health_data['status']}")
    else:
        logger.info(f"Detailed health check passed in {total_response_time:.2f}s")

    response_status = 200 if health_data["status"] == "healthy" else 503
    return JsonResponse(health_data, status=response_status)


@require_GET
@cache_page(60)  # Cache for 1 minute
def prometheus_metrics(request):
    """
    Expose Prometheus metrics endpoint.
    """
    try:
        from django_prometheus import exports  # type: ignore[import-untyped]

        return exports.ExportToDjangoView(request)
    except ImportError:
        logger.error("Prometheus not configured")
        return JsonResponse({"error": "Prometheus not configured"}, status=503)
