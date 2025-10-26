"""
Production settings overrides for Bus Kiosk Backend.
This file contains production-specific settings that override the base settings.

Usage:
    DJANGO_SETTINGS_MODULE=bus_kiosk_backend.production_settings
"""

import os

from . import settings

# ===========================================
# PRODUCTION SECURITY OVERRIDES
# ===========================================

# DEBUG must be False in production
DEBUG = False

# Production ALLOWED_HOSTS (no localhost)
ALLOWED_HOSTS = [
    "easypool.in",
    "www.easypool.in",
    "api.easypool.in",  # If using separate API domain
]

# Add environment variable hosts if specified
if os.getenv("ALLOWED_HOSTS"):
    ALLOWED_HOSTS.extend([host.strip() for host in os.getenv("ALLOWED_HOSTS", "").split(",")])

# Production CORS (HTTPS only, no localhost)
CORS_ALLOWED_ORIGINS = [
    "https://easypool.in",
    "https://www.easypool.in",
    "https://app.easypool.in",  # If using separate app domain
]

# Production API docs servers
settings.SPECTACULAR_SETTINGS["SERVERS"] = [
    {"url": "https://api.easypool.in", "description": "Production API"},
]

# Production renderer classes (no browsable API)
settings.REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [
    "rest_framework.renderers.JSONRenderer",
]

# Enable response validation in production
OPENAPI_VALIDATE_RESPONSES = True

# Remove test app from production
if "tests" in settings.INSTALLED_APPS:
    settings.INSTALLED_APPS.remove("tests")

# ===========================================
# PRODUCTION PERFORMANCE SETTINGS
# ===========================================

# Higher connection pool for production
if "default" in settings.DATABASES and settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    settings.DATABASES["default"]["CONN_MAX_AGE"] = 300  # 5 minutes
    settings.DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# Production cache settings (longer timeouts)
if "default" in settings.CACHES:
    settings.CACHES["default"]["TIMEOUT"] = 1800  # 30 minutes
if "api_cache" in settings.CACHES:
    settings.CACHES["api_cache"]["TIMEOUT"] = 7200  # 2 hours

# ===========================================
# PRODUCTION LOGGING
# ===========================================

# Ensure file logging is enabled in production
USE_FILE_LOGGING = True

# Production log levels
LOGGING = settings.LOGGING
LOGGING["loggers"]["django"]["level"] = "WARNING"
LOGGING["loggers"]["bus_kiosk_backend"]["level"] = "INFO"

# ===========================================
# PRODUCTION MONITORING
# ===========================================

# Enable all Prometheus metrics in production
PROMETHEUS_METRICS_EXPORT_PORT = int(os.getenv("PROMETHEUS_METRICS_EXPORT_PORT", "8001"))
PROMETHEUS_METRICS_EXPORT_ADDRESS = os.getenv("PROMETHEUS_METRICS_EXPORT_ADDRESS", "127.0.0.1")
