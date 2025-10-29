"""
CI/CD testing settings.
Optimized for fast test execution in CI pipelines (GitHub Actions, GitLab CI, etc.).

Fortune 500 Pattern:
- In-memory database for speed
- Minimal middleware for faster tests
- Console-only logging (no file I/O)
- Disabled external services (Celery, Redis, Firebase)
"""

from datetime import timedelta
import os
from pathlib import Path

# Import all base settings
from .base import *  # noqa: F403

# CI/CD overrides
DEBUG = True  # Enable debug for better error messages in CI logs
SECRET_KEY = "ci-test-secret-key-not-for-production"
ENCRYPTION_KEY = "dKWpt_QqCynKj9NhnY6Fs7cbLd-itxLzGOfbcTwTJtM="  # Test key

# Allowed hosts for CI
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

# CSRF trusted origins for CI
CSRF_TRUSTED_ORIGINS = [
    "http://testserver",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# CI Database - In-memory SQLite for maximum speed
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",  # In-memory database (fastest for CI)
        "TEST": {
            "NAME": ":memory:",
        },
    }
}

# CI Cache - In-memory only (no Redis)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "ci-cache",
    },
    "api_cache": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "ci-api-cache",
    },
}

# CI Channel Layers - In-memory (no Redis)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# CI Celery - Synchronous execution (no broker needed)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"

# Use faster password hasher for CI tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# CI Logging - Console only (no file I/O for speed)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",  # Reduce noise in CI logs
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "bus_kiosk_backend": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Disable OpenAPI validation in CI tests (faster execution)
OPENAPI_VALIDATE_REQUESTS = False
OPENAPI_VALIDATE_RESPONSES = False
OPENAPI_FAIL_ON_ERROR = False

# Minimal middleware for CI tests (faster request processing)
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # CSRF middleware removed for API testing
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# REST Framework CI settings - Override authentication for easier testing
REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = [  # noqa: F405
    "rest_framework_simplejwt.authentication.JWTAuthentication",
    "kiosks.authentication.KioskJWTAuthentication",
    "rest_framework.authentication.SessionAuthentication",
]
REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] = []  # No global permissions for tests  # noqa: F405
REST_FRAMEWORK["TEST_REQUEST_DEFAULT_FORMAT"] = "json"  # noqa: F405

# Disable security features for CI testing
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_SSL_REDIRECT = False

# Google Maps API Key (test value for CI)
GOOGLE_MAPS_API_KEY = "test-api-key-for-ci"

print("[CI] CI/CD settings loaded successfully")
print("[CI] Database: In-memory SQLite")
print("[CI] Celery: Synchronous (TASK_ALWAYS_EAGER=True)")
print("[CI] Cache: In-memory")
print("[CI] Logging: Console only")
