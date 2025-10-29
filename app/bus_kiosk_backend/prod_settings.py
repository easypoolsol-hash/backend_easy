"""
Production settings for Django project.
Inherits from base settings.py with production-specific overrides.
"""

import os

from .settings import LOGGING

# Production overrides - NO DEBUG ALLOWED
DEBUG = False  # Hard-coded, cannot be overridden by environment

# Production CORS (HTTPS only)
CORS_ALLOWED_ORIGINS = [
    "https://easypool.in",
    "https://www.easypool.in",
    "https://api.easypool.in",
]

# Production security (enforce HTTPS)
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True

# Production logging (less verbose)
LOGGING["root"]["level"] = "WARNING"
LOGGING["loggers"]["django"]["level"] = "WARNING"
LOGGING["loggers"]["bus_kiosk_backend"]["level"] = "INFO"

# Production database (PostgreSQL required)
if not os.getenv("DB_ENGINE") == "django.db.backends.postgresql":
    raise ValueError("Production must use PostgreSQL database")

# Production cache (Redis required)
if not os.getenv("REDIS_URL"):
    raise ValueError("Production must use Redis cache")

# Production channel layers (Redis required)
if not os.getenv("REDIS_URL"):
    raise ValueError("Production must use Redis for WebSocket channels")

# Production Celery (required for background tasks)
if not os.getenv("CELERY_BROKER_URL"):
    raise ValueError("Production must configure Celery broker")
