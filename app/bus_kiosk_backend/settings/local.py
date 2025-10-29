"""
Local development settings.
Inherits from base.py with development-specific overrides.

This is the ONLY place where .env files are loaded (Fortune 500 pattern).
Production NEVER uses .env files - only environment variable injection.
"""

import os
from pathlib import Path

# Load .env ONLY in local development (Fortune 500 pattern)
try:
    from dotenv import load_dotenv

    # Look for .env in backend_easy directory (parent of app)
    env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[LOCAL] Loaded .env from: {env_path}")
    else:
        print(f"[LOCAL] No .env file found at: {env_path}")
except ImportError:
    print("[LOCAL] python-dotenv not installed - using system environment variables only")

# Import all base settings
from .base import *  # noqa: F403

# Development overrides
DEBUG = True

# Development secret key (never use in production)
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-not-for-production-change-in-env-file")

# Development encryption key (override from .env if provided)
ENCRYPTION_KEY = os.getenv(
    "ENCRYPTION_KEY",
    "dKWpt_QqCynKj9NhnY6Fs7cbLd-itxLzGOfbcTwTJtM=",  # Test key
)

# CORS for development (allow localhost)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # Flutter dev server
    "http://127.0.0.1:3000",
    "http://localhost:8000",  # Django dev server
    "http://127.0.0.1:8000",
    "https://easypool.in",
    "https://www.easypool.in",
    "https://api.easypool.in",
]

# Allowed hosts for development
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "easypool.in",
    "www.easypool.in",
    "api.easypool.in",
]

# CSRF trusted origins for development
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://easypool.in",
    "https://www.easypool.in",
    "https://api.easypool.in",
]

# Disable production security features for development
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_SSL_REDIRECT = False

# Development logging (more verbose)
LOGGING["root"]["level"] = "DEBUG"  # noqa: F405  # type: ignore[index]
LOGGING["loggers"]["django"]["level"] = "DEBUG"  # noqa: F405  # type: ignore[index]
LOGGING["loggers"]["bus_kiosk_backend"]["level"] = "DEBUG"  # noqa: F405  # type: ignore[index]

# Development database (SQLite for simplicity)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    }
}

# Development cache (local memory - no Redis required)
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

# Development channel layers (in-memory - no Redis required)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# Development Celery (use local Redis if available, or disable)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_TASK_ALWAYS_EAGER = False  # Set to True to run tasks synchronously (no Celery worker needed)

# Add DRF Browsable API in development
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [  # noqa: F405
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",  # Development only
]

# Add localhost to DRF Spectacular servers
SPECTACULAR_SETTINGS["SERVERS"] = [  # noqa: F405
    {"url": "http://localhost:8000", "description": "Local development"},
    {"url": "https://api.easypool.in", "description": "Production API"},
]

print("[LOCAL] Development settings loaded successfully")
print(f"[LOCAL] DEBUG = {DEBUG}")
print(f"[LOCAL] Database: SQLite at {DATABASES['default']['NAME']}")
print("[LOCAL] Cache: In-memory")
print("[LOCAL] Channel Layers: In-memory")
