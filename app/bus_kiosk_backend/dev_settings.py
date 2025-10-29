"""
Development settings for Django project.
Inherits from base settings.py with development-specific overrides.
"""

# Import all base settings first
from .settings import *  # noqa: F403

# Import specific settings that will be modified
from .settings import (
    ALLOWED_HOSTS,
    BASE_DIR,
    CORS_ALLOWED_ORIGINS,
    LOGGING,
)

# Development overrides
DEBUG = True
SECRET_KEY = "dev-secret-key-not-for-production"

# CORS for development (allow localhost)
CORS_ALLOWED_ORIGINS.extend(
    [
        "http://localhost:3000",  # Flutter dev server
        "http://127.0.0.1:3000",
        "http://localhost:8000",  # Django dev server (for testing)
    ]
)

ALLOWED_HOSTS.extend(
    [
        "localhost",
        "127.0.0.1",
    ]
)

# Disable production security features for development
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_SSL_REDIRECT = False

# Development logging (more verbose)
LOGGING["root"]["level"] = "DEBUG"  # type: ignore
LOGGING["loggers"]["django"]["level"] = "DEBUG"  # type: ignore
LOGGING["loggers"]["bus_kiosk_backend"]["level"] = "DEBUG"  # type: ignore

# Development database (SQLite for simplicity)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Development cache (local memory)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
        "KEY_PREFIX": "bus_kiosk_dev",
        "TIMEOUT": 300,
    },
    "api_cache": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "api-cache-dev",
        "KEY_PREFIX": "api_dev",
        "TIMEOUT": 3600,
    },
}

# Development channel layers (in-memory for simplicity)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# Development Celery (optional - can be disabled)
# CELERY_BROKER_URL = None  # Disable Celery if Redis not available
