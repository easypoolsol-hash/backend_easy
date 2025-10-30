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

import json
import os

import firebase_admin
from firebase_admin import credentials

# Import all base settings
from .base import *  # noqa: F403

# Import security settings
from .security import *  # noqa: F403

# Production: DEBUG must be False (hard-coded, no override)
DEBUG = False

# Production: SECRET_KEY must be injected via environment (no fallback)
SECRET_KEY = os.environ["SECRET_KEY"]  # Fails fast if not set

# Production: ENCRYPTION_KEY must be injected via environment (no fallback)
ENCRYPTION_KEY = os.environ["ENCRYPTION_KEY"]  # Fails fast if not set

# Production: Strict allowed hosts (no localhost)
ALLOWED_HOSTS = [
    "easypool.in",
    "www.easypool.in",
    "api.easypool.in",
]

# Add environment variable hosts if specified (for flexibility in multi-region deployments)
if os.getenv("ALLOWED_HOSTS"):
    additional_hosts = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "").split(",")]
    ALLOWED_HOSTS.extend(additional_hosts)

# Production CORS - Extend base config with production backend URLs
CORS_ALLOWED_ORIGINS = [
    *CORS_ALLOWED_ORIGINS,  # noqa: F405
    "https://backendeasy-683213759629.asia-south1.run.app",
    "https://backendeasy-lela6xnh4q-el.a.run.app",
]

# Production CSRF - Extend base config with production backend URLs
# Hardcoded only - no injection for security
CSRF_TRUSTED_ORIGINS = [
    *CSRF_TRUSTED_ORIGINS,  # noqa: F405
    "https://backendeasy-683213759629.asia-south1.run.app",
    "https://backendeasy-lela6xnh4q-el.a.run.app",
]

# Production security
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = False  # Cloud Run handles HTTPS
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Firebase - Read from Secret Manager (required)
_firebase_key = os.environ["FIREBASE_SERVICE_ACCOUNT_KEY"]
cred = credentials.Certificate(json.loads(_firebase_key))
firebase_admin.initialize_app(cred)

# Production logging (less verbose, file-based)
LOGGING["root"]["level"] = "WARNING"  # noqa: F405  # type: ignore[index]
LOGGING["loggers"]["django"]["level"] = "WARNING"  # noqa: F405  # type: ignore[index]
LOGGING["loggers"]["bus_kiosk_backend"]["level"] = "INFO"  # noqa: F405  # type: ignore[index]

# Production database (PostgreSQL required)
# Google Cloud Run connects to Cloud SQL via Unix socket
# DATABASE_URL format: postgresql://user:pass@/dbname?host=/cloudsql/PROJECT:REGION:INSTANCE

import dj_database_url  # noqa: E402

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("Production requires DATABASE_URL environment variable")

# Parse DATABASE_URL (supports Cloud SQL Unix socket connections)
DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,  # Connection pooling (10 minutes)
        conn_health_checks=True,
    )
}

# Ensure it's PostgreSQL
if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ValueError(f"Production requires PostgreSQL. Got: {DATABASES['default']['ENGINE']}")

# Add additional PostgreSQL options
DATABASES["default"]["OPTIONS"] = {
    "connect_timeout": 10,
    "options": "-c timezone=UTC",
}

# Production cache (Redis required)
if not os.getenv("REDIS_URL"):
    raise ValueError("Production requires Redis cache. Set REDIS_URL environment variable (e.g., redis://127.0.0.1:6379/0)")

redis_url = os.environ["REDIS_URL"]

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

# Production channel layers (Redis required for WebSocket)
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

# Production Celery (Redis required)
if not os.getenv("CELERY_BROKER_URL"):
    raise ValueError("Production requires Celery broker. Set CELERY_BROKER_URL environment variable (e.g., redis://127.0.0.1:6379/0)")

CELERY_BROKER_URL = os.environ["CELERY_BROKER_URL"]

# Production: Google Maps API Key (required)
if not os.getenv("GOOGLE_MAPS_API_KEY"):
    raise ValueError("Production requires Google Maps API Key. Set GOOGLE_MAPS_API_KEY environment variable")

GOOGLE_MAPS_API_KEY = os.environ["GOOGLE_MAPS_API_KEY"]

# Production: Firebase Admin SDK (required for authentication)
if not os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY_PATH"):
    raise ValueError("Production requires Firebase service account. Set FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable")

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
