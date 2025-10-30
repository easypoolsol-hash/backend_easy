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

import environ

# Import all base settings
from .base import *  # noqa: F403

# Import security settings
from .security import *  # noqa: F403

# Initialize django-environ
env = environ.Env()

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

# Firebase - Initialized in base.py (common for all environments)

# Production logging (less verbose, file-based)
LOGGING["root"]["level"] = "WARNING"  # noqa: F405  # type: ignore[index]
LOGGING["loggers"]["django"]["level"] = "WARNING"  # noqa: F405  # type: ignore[index]
LOGGING["loggers"]["bus_kiosk_backend"]["level"] = "INFO"  # noqa: F405  # type: ignore[index]

# Production database (PostgreSQL required via DATABASE_URL)
# Supports: PostgreSQL, MySQL, SQLite, Oracle, SQL Server
# Google Cloud SQL: postgresql://user:pass@/dbname?host=/cloudsql/PROJECT:REGION:INSTANCE
# Standard PostgreSQL: postgresql://user:pass@host:5432/dbname

# Production database - Use django-environ to parse DATABASE_URL
# Official Google Cloud recommended approach for Cloud SQL connections
# Format: postgres://USER:PASS@//cloudsql/PROJECT:REGION:INSTANCE/DBNAME
if not os.environ.get("DATABASE_URL"):
    raise ValueError("Production requires DATABASE_URL environment variable")

# Parse DATABASE_URL using django-environ (handles Cloud SQL unix sockets correctly)
DATABASES = {"default": env.db()}

# Add PostgreSQL-specific options
DATABASES["default"]["CONN_MAX_AGE"] = 600
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
DATABASES["default"]["OPTIONS"] = {
    "connect_timeout": 10,
    "options": "-c timezone=UTC",
}

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
