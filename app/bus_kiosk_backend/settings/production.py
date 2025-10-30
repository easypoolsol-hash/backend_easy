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

# Production security (HTTPS enforcement)
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Production logging (less verbose, file-based)
LOGGING["root"]["level"] = "WARNING"  # noqa: F405  # type: ignore[index]
LOGGING["loggers"]["django"]["level"] = "WARNING"  # noqa: F405  # type: ignore[index]
LOGGING["loggers"]["bus_kiosk_backend"]["level"] = "INFO"  # noqa: F405  # type: ignore[index]

# Production database (PostgreSQL required)
if os.getenv("DB_ENGINE") != "django.db.backends.postgresql":
    raise ValueError("Production requires PostgreSQL database. Set DB_ENGINE=django.db.backends.postgresql")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DB_NAME"],  # Fails fast if not set
        "USER": os.environ["DB_USER"],  # Fails fast if not set
        "PASSWORD": os.environ["DB_PASSWORD"],  # Fails fast if not set
        "HOST": os.environ["DB_HOST"],  # Fails fast if not set
        "PORT": os.getenv("DB_PORT", "5432"),
        "OPTIONS": {
            "connect_timeout": 10,
            "options": "-c timezone=UTC",
        },
        "CONN_MAX_AGE": 600,  # Connection pooling (10 minutes)
        "CONN_HEALTH_CHECKS": True,
    }
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
