"""
Development settings.
For dev.easypool.in - production-like environment with debugging enabled.

Fortune 500 Pattern:
- Uses real PostgreSQL (Cloud SQL) - NO SQLite fallback
- Secrets from GCP Secret Manager
- DEBUG = True for troubleshooting
- Relaxed security for development
- In-memory cache/channels for simplicity
"""

import os
import re

# Import all base settings
from .base import *  # noqa: F403

# Import security settings
from .security import *  # noqa: F403

# Development: DEBUG enabled
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# Development: SECRET_KEY from environment (required)
SECRET_KEY = os.environ["SECRET_KEY"]  # Fails fast if not set

# Development: ENCRYPTION_KEY from environment (required)
ENCRYPTION_KEY = os.environ["ENCRYPTION_KEY"]  # Fails fast if not set

# Development: ALLOWED_HOSTS from environment ONLY (no hardcoded defaults)
# Terraform/Cloud Run injects the correct Cloud Run URL
ALLOWED_HOSTS = [host.strip() for host in os.environ.get("ALLOWED_HOSTS", "").split(",") if host.strip()]
if not ALLOWED_HOSTS:
    raise RuntimeError(
        "CRITICAL ERROR: ALLOWED_HOSTS not set in environment!\n"
        "Development requires explicit allowed hosts for security.\n"
        "Check that ALLOWED_HOSTS is configured in Terraform."
    )

# Development CORS - from environment ONLY (no hardcoded defaults)
# Terraform/Cloud Run injects frontend URLs
_cors_origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in _cors_origins_env.split(",") if origin.strip()]

# Development CSRF - from environment ONLY (no hardcoded defaults)
# Terraform/Cloud Run injects trusted origins
_csrf_origins_env = os.getenv("CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in _csrf_origins_env.split(",") if origin.strip()]

# Development: Minimal HTTPS security
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_SSL_REDIRECT = False  # Cloud Run handles HTTPS
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Development logging (verbose)
LOGGING["root"]["level"] = "INFO"  # noqa: F405  # type: ignore[index]
LOGGING["loggers"]["django"]["level"] = "DEBUG"  # noqa: F405  # type: ignore[index]
LOGGING["loggers"]["bus_kiosk_backend"]["level"] = "DEBUG"  # noqa: F405  # type: ignore[index]

# Development database - DATABASE_URL REQUIRED (NO SQLite fallback)
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "CRITICAL ERROR: DATABASE_URL not set!\n"
        "Development environment requires Cloud SQL connection.\n"
        "SQLite is NOT allowed in Cloud Run (ephemeral storage).\n"
        "Check that DATABASE_URL secret is configured in Terraform."
    )

# Parse DATABASE_URL for Cloud SQL Unix socket format
if "?host=/cloudsql/" in DATABASE_URL or "@//cloudsql/" in DATABASE_URL:
    # Cloud SQL Unix socket format
    if "?host=/cloudsql/" in DATABASE_URL:
        # Query parameter format
        match = re.match(r"postgres(?:ql)?://([^:]+):([^@]+)@/([^?]+)\?host=(.+)", DATABASE_URL)
        if match:
            user, password, dbname, host = match.groups()
        else:
            raise ValueError(f"Invalid Cloud SQL DATABASE_URL format: {DATABASE_URL}")
    else:
        # Path format
        match = re.match(r"postgres(?:ql)?://([^:]+):([^@]+)@//cloudsql/([^/]+)/(.+)", DATABASE_URL)
        if match:
            user, password, instance, dbname = match.groups()
            host = f"/cloudsql/{instance}"
        else:
            raise ValueError(f"Invalid Cloud SQL DATABASE_URL format: {DATABASE_URL}")

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": dbname,
            "USER": user,
            "PASSWORD": password,
            "HOST": host,  # /cloudsql/PROJECT:REGION:INSTANCE
            "OPTIONS": {
                "connect_timeout": 10,
                "options": "-c timezone=UTC",
            },
            # Connection pooling for Cloud Run (prevent connection exhaustion)
            # Cloud Run scales horizontally, so we need to limit per-instance connections
            "CONN_MAX_AGE": 60,  # Reduced from 600 to 60 seconds (1 minute)
            "CONN_HEALTH_CHECKS": True,
            # Set max connections per instance (Cloud Run best practice)
            "POOL_SIZE": int(os.getenv("DB_POOL_SIZE", "5")),  # Max connections per instance
        }
    }
else:
    # Standard PostgreSQL URL format
    match = re.match(r"postgres(?:ql)?://([^:]+):([^@]+)@([^:]+):?(\d+)?/(.+)", DATABASE_URL)
    if match:
        user, password, host, port, dbname = match.groups()
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": dbname,
                "USER": user,
                "PASSWORD": password,
                "HOST": host,
                "PORT": port or "5432",
                "OPTIONS": {
                    "connect_timeout": 10,
                    "options": "-c timezone=UTC",
                },
                # Connection pooling for Cloud Run (prevent connection exhaustion)
                "CONN_MAX_AGE": 60,  # Reduced from 600 to 60 seconds (1 minute)
                "CONN_HEALTH_CHECKS": True,
                "POOL_SIZE": int(os.getenv("DB_POOL_SIZE", "5")),  # Max connections per instance
            }
        }
    else:
        raise ValueError(f"Invalid DATABASE_URL format: {DATABASE_URL}")

# Development cache - In-memory (simple, no Redis needed)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "dev-cache",
    },
    "api_cache": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "dev-api-cache",
    },
}

# Development channel layers - In-memory (single-instance)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# Development Celery - Run tasks synchronously (no broker needed)
CELERY_BROKER_URL = "memory://"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Development: Google Maps API Key - Optional
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "test-api-key-dev")

# Development: Keep DRF Browsable API for testing
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [  # noqa: F405
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",  # Keep for development
]

# Development: API docs show dev server
SPECTACULAR_SETTINGS["SERVERS"] = [  # noqa: F405
    {"url": os.getenv("DEV_URL", "https://easypool-backend-dev.run.app"), "description": "Development API"},
]

# =============================================================================
# BIGQUERY REAL-TIME STREAMING (Development Only)
# =============================================================================
# Sends boarding events to BigQuery immediately after verification
# Perfect for A/B testing - see results in Looker Studio instantly!
BIGQUERY_STREAMING_ENABLED = True
BIGQUERY_PROJECT_ID = "easypool-backend"
BIGQUERY_DATASET_ID = "ml_analytics"

# =============================================================================
# KIOSK METRICS REAL-TIME STREAMING (Development Only)
# =============================================================================
# Sends kiosk health metrics to Cloud Monitoring on every heartbeat
# Dashboard updates in real-time when kiosk sends heartbeat!
KIOSK_METRICS_STREAMING_ENABLED = True

print("[DEVELOPMENT] Development settings loaded successfully")
print(f"[DEVELOPMENT] DEBUG = {DEBUG}")
print("[DEVELOPMENT] Database: PostgreSQL (Cloud SQL)")
print("[DEVELOPMENT] Cache: In-memory")
print("[DEVELOPMENT] Channel Layers: In-memory")
print("[DEVELOPMENT] Celery: Synchronous (no broker)")
print("[DEVELOPMENT] HTTPS: Not enforced (Cloud Run handles it)")
print("[DEVELOPMENT] BigQuery Streaming: ENABLED (real-time analytics)")
print("[DEVELOPMENT] Kiosk Metrics Streaming: ENABLED (real-time dashboard)")
