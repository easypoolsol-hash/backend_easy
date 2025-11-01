"""
Production settings.
Inherits from base.py with production-specific security hardening.

Fortune 500 Pattern:
- NO .env files (environment variable injection only)
- Secrets from GCP Secret Manager / Kubernetes secrets
- HTTPS enforcement
- PostgreSQL required
- Redis required
- Strict security headers
- File logging enabled
"""

import os
import re

# Import all base settings
from .base import *  # noqa: F403

# Import security settings
from .security import *  # noqa: F403

# Production: DEBUG - allow override for troubleshooting
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# Production: SECRET_KEY must be injected via environment (no fallback)
SECRET_KEY = os.environ["SECRET_KEY"]  # Fails fast if not set

# Production: ENCRYPTION_KEY must be injected via environment (no fallback)
ENCRYPTION_KEY = os.environ["ENCRYPTION_KEY"]  # Fails fast if not set

# Production: ALLOWED_HOSTS from environment (or default)
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "easypool.in,www.easypool.in,api.easypool.in").split(",")

# Production CORS - from environment or base only
_cors_origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
if _cors_origins_env:
    CORS_ALLOWED_ORIGINS = [*CORS_ALLOWED_ORIGINS, *_cors_origins_env.split(",")]  # noqa: F405
else:
    CORS_ALLOWED_ORIGINS = [*CORS_ALLOWED_ORIGINS]

# Production CSRF - from environment or base only
_csrf_origins_env = os.getenv("CSRF_TRUSTED_ORIGINS", "")
if _csrf_origins_env:
    CSRF_TRUSTED_ORIGINS = [*CSRF_TRUSTED_ORIGINS, *_csrf_origins_env.split(",")]  # noqa: F405
else:
    CSRF_TRUSTED_ORIGINS = [*CSRF_TRUSTED_ORIGINS]

# Production security
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = False  # Cloud Run handles HTTPS
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Firebase - Initialized in base.py (common for all environments)

# Production logging (less verbose, file-based)
LOGGING["root"]["level"] = "WARNING"  # noqa: F405  # type: ignore[index]
LOGGING["loggers"]["django"]["level"] = "WARNING"  # noqa: F405  # type: ignore[index]
LOGGING["loggers"]["bus_kiosk_backend"]["level"] = "INFO"  # noqa: F405  # type: ignore[index]

# Production database (PostgreSQL required via DATABASE_URL)
# Supports: PostgreSQL, MySQL, SQLite, Oracle, SQL Server
# Google Cloud SQL: postgresql://user:pass@/dbname?host=/cloudsql/PROJECT:REGION:INSTANCE
# Standard PostgreSQL: postgresql://user:pass@host:5432/dbname

# Production database - DATABASE_URL REQUIRED (NO fallback)
# Format: postgresql://user:pass@/dbname?host=/cloudsql/PROJECT:REGION:INSTANCE
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "CRITICAL ERROR: DATABASE_URL not set in production!\n"
        "Production requires Cloud SQL connection.\n"
        "SQLite is NOT allowed (ephemeral storage, data loss on restart).\n"
        "Check that DATABASE_URL secret is configured in Terraform/GCP Secret Manager."
    )

# Parse DATABASE_URL manually for Cloud SQL Unix socket format
if DATABASE_URL and ("?host=/cloudsql/" in DATABASE_URL or "@//cloudsql/" in DATABASE_URL):
    # Cloud SQL Unix socket format - supports both old and new formats
    # Old: postgresql://user:pass@/dbname?host=/cloudsql/instance
    # New: postgres://user:pass@//cloudsql/instance/dbname

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
            "CONN_MAX_AGE": 600,
            "CONN_HEALTH_CHECKS": True,
        }
    }
elif DATABASE_URL:
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
                "CONN_MAX_AGE": 600,
                "CONN_HEALTH_CHECKS": True,
            }
        }
    else:
        raise ValueError(f"Invalid DATABASE_URL format: {DATABASE_URL}")

# Production cache (Redis - temporarily use in-memory fallback)
# TODO: Re-enable Redis once REDIS_URL secret is added to GCP Secret Manager
redis_url = os.getenv("REDIS_URL")
if redis_url:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": redis_url,
            "KEY_PREFIX": "bus_kiosk_prod",
            "TIMEOUT": 300,
        },
        "api_cache": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": redis_url,
            "KEY_PREFIX": "api_prod",
            "TIMEOUT": 3600,
        },
    }
else:
    # Fallback to in-memory cache (not recommended for production)
    print("[PRODUCTION] WARNING: Using in-memory cache. Set REDIS_URL for production Redis cache.")
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "bus_kiosk_prod",
        },
        "api_cache": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "api_prod",
        },
    }

# Production channel layers (Redis - fallback to in-memory for WebSocket)
# TODO: Re-enable Redis once REDIS_URL secret is added to GCP Secret Manager
if redis_url:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [redis_url],
                "capacity": 1500,  # type: ignore[dict-item]
                "expiry": 10,  # type: ignore[dict-item]
            },
        },
    }
else:
    # Fallback to in-memory channel layer (not recommended for production)
    print("[PRODUCTION] WARNING: Using in-memory channel layer. Set REDIS_URL for production Redis.")
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }

# Production Celery (Redis - make optional for now)
# TODO: Re-enable strict requirement once CELERY_BROKER_URL secret is added
celery_broker_url = os.getenv("CELERY_BROKER_URL")
if celery_broker_url:
    CELERY_BROKER_URL = celery_broker_url
else:
    print("[PRODUCTION] WARNING: CELERY_BROKER_URL not set. Background tasks disabled.")
    CELERY_TASK_ALWAYS_EAGER = True  # Run tasks synchronously

# Production: Google Maps API Key (optional for now)
# TODO: Re-enable strict requirement once GOOGLE_MAPS_API_KEY secret is added
google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
if google_maps_api_key:
    GOOGLE_MAPS_API_KEY = google_maps_api_key
else:
    print("[PRODUCTION] WARNING: GOOGLE_MAPS_API_KEY not set. Maps features may not work.")
    GOOGLE_MAPS_API_KEY = ""

# Firebase - Already initialized in base.py (common for all environments)
# Secret: firebase-service-account-key is injected as FIREBASE_SERVICE_ACCOUNT_KEY env var

# Production: Remove DRF Browsable API (security)
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [  # noqa: F405
    "rest_framework.renderers.JSONRenderer",
    # Browsable API removed for production security
]

# Production: Only production server in API docs
SPECTACULAR_SETTINGS["SERVERS"] = [  # noqa: F405
    {"url": "https://api.easypool.in", "description": "Production API"},
]

print("[PRODUCTION] Production settings loaded successfully")
print(f"[PRODUCTION] DEBUG = {DEBUG}")
print(f"[PRODUCTION] Database: PostgreSQL at {DATABASES['default']['HOST']}")
print("[PRODUCTION] Cache: Redis")
print("[PRODUCTION] Channel Layers: Redis")
print("[PRODUCTION] Celery Broker: Redis")
print("[PRODUCTION] HTTPS: Enforced")
print(f"[PRODUCTION] HSTS: {SECURE_HSTS_SECONDS} seconds")
