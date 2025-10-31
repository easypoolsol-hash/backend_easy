"""
Staging settings.
Production-like environment for testing before production deployment.

Fortune 500 Pattern:
- Uses real PostgreSQL (Cloud SQL)
- Secrets from GCP Secret Manager
- Relaxed requirements (Redis/Celery optional)
- DEBUG can be enabled for troubleshooting
- Similar to production but more forgiving
"""

import os

# Import all base settings
from .base import *  # noqa: F403

# Import security settings
from .security import *  # noqa: F403

# Staging: DEBUG can be True for easier troubleshooting
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# Staging: SECRET_KEY from environment
SECRET_KEY = os.environ.get("SECRET_KEY", "staging-secret-key-change-in-production")

# Staging: ENCRYPTION_KEY from environment
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "dKWpt_QqCynKj9NhnY6Fs7cbLd-itxLzGOfbcTwTJtM=")

# Staging: Flexible allowed hosts
ALLOWED_HOSTS = ["*"]  # Wide open for staging testing

# Allow environment variable hosts override
if os.getenv("ALLOWED_HOSTS"):
    additional_hosts = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "").split(",")]
    ALLOWED_HOSTS = additional_hosts

# Staging CORS - from environment or base only
_cors_origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
if _cors_origins_env:
    CORS_ALLOWED_ORIGINS = [*CORS_ALLOWED_ORIGINS, *_cors_origins_env.split(",")]  # noqa: F405
else:
    # Default CORS origins for staging (localhost for testing)
    CORS_ALLOWED_ORIGINS = [
        *CORS_ALLOWED_ORIGINS,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

# Staging CSRF - from environment or base only
_csrf_origins_env = os.getenv("CSRF_TRUSTED_ORIGINS", "")
if _csrf_origins_env:
    CSRF_TRUSTED_ORIGINS = [*CSRF_TRUSTED_ORIGINS, *_csrf_origins_env.split(",")]  # noqa: F405
else:
    # Default CSRF origins for staging (localhost for testing)
    CSRF_TRUSTED_ORIGINS = [
        *CSRF_TRUSTED_ORIGINS,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

# Staging: Basic HTTPS security
SECURE_HSTS_SECONDS = 3600  # 1 hour
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_SSL_REDIRECT = False  # Cloud Run handles HTTPS
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Firebase - Initialized in base.py (common for all environments)

# Staging logging
LOGGING["root"]["level"] = "INFO"  # noqa: F405  # type: ignore[index]
LOGGING["loggers"]["django"]["level"] = "INFO"  # noqa: F405  # type: ignore[index]
LOGGING["loggers"]["bus_kiosk_backend"]["level"] = "DEBUG"  # noqa: F405  # type: ignore[index]

# Staging database - Parse DATABASE_URL if available
database_url = os.environ.get("DATABASE_URL")
if database_url:
    # Parse DATABASE_URL manually (simple parsing for Cloud SQL)
    # Supports both formats:
    # 1. Google Cloud format: postgres://user:pass@//cloudsql/PROJECT:REGION:INSTANCE/dbname
    # 2. Query parameter format: postgresql://user:pass@/dbname?host=/cloudsql/instance
    import re

    # Check for Google Cloud format (path-based with //)
    if "@//cloudsql/" in database_url:
        # Format: postgres://user:pass@//cloudsql/PROJECT:REGION:INSTANCE/dbname
        match = re.match(r"postgres(?:ql)?://([^:]+):([^@]+)@//cloudsql/([^/]+)/(.+)", database_url)
        if match:
            user, password, instance, dbname = match.groups()
            host = f"/cloudsql/{instance}"
            DATABASES = {
                "default": {
                    "ENGINE": "django.db.backends.postgresql",
                    "NAME": dbname,
                    "USER": user,
                    "PASSWORD": password,
                    "HOST": host,
                    "OPTIONS": {
                        "connect_timeout": 10,
                        "options": "-c timezone=UTC",
                    },
                    "CONN_MAX_AGE": 600,
                    "CONN_HEALTH_CHECKS": True,
                }
            }
    # Check for query parameter format
    elif "?host=/cloudsql/" in database_url:
        # Format: postgresql://user:pass@/dbname?host=/cloudsql/instance
        match = re.match(r"postgres(?:ql)?://([^:]+):([^@]+)@/([^?]+)\?host=(.+)", database_url)
        if match:
            user, password, dbname, host = match.groups()
            DATABASES = {
                "default": {
                    "ENGINE": "django.db.backends.postgresql",
                    "NAME": dbname,
                    "USER": user,
                    "PASSWORD": password,
                    "HOST": host,
                    "OPTIONS": {
                        "connect_timeout": 10,
                        "options": "-c timezone=UTC",
                    },
                    "CONN_MAX_AGE": 600,
                    "CONN_HEALTH_CHECKS": True,
                }
            }
    else:
        # Standard PostgreSQL URL format
        # Format: postgresql://user:pass@host:port/dbname
        match = re.match(r"postgres(?:ql)?://([^:]+):([^@]+)@([^:]+):?(\d+)?/(.+)", database_url)
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
    # Fallback to SQLite for local staging testing
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "staging.sqlite3",  # noqa: F405
        }
    }

# Staging cache - Redis optional, fallback to dummy cache
_staging_redis_url = os.getenv("REDIS_URL")
if _staging_redis_url:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _staging_redis_url,
            "KEY_PREFIX": "bus_kiosk_staging",
            "TIMEOUT": 300,
        },
        "api_cache": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _staging_redis_url,
            "KEY_PREFIX": "api_staging",
            "TIMEOUT": 3600,
        },
    }
else:
    # Dummy cache (no caching, but won't crash)
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        },
        "api_cache": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        },
    }

# Staging channel layers - Redis optional, fallback to in-memory
if _staging_redis_url:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [_staging_redis_url],
                "capacity": 1500,  # type: ignore[dict-item]
                "expiry": 10,  # type: ignore[dict-item]
            },
        },
    }
else:
    # In-memory channel layer (single-instance only)
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }

# Staging Celery - Optional, runs synchronously if no broker
celery_broker = os.getenv("CELERY_BROKER_URL")
if celery_broker:
    CELERY_BROKER_URL = celery_broker
    CELERY_TASK_ALWAYS_EAGER = False
else:
    # No broker: Run tasks synchronously (blocking)
    CELERY_BROKER_URL = "memory://"
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

# Staging: Google Maps API Key - Optional
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "test-api-key-staging")

# Staging: Firebase - Optional (already handled in base.py with graceful fallback)
# No additional config needed

# Staging: Keep DRF Browsable API for testing
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [  # noqa: F405
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",  # Keep for staging
]

# Staging: API docs show staging server
SPECTACULAR_SETTINGS["SERVERS"] = [  # noqa: F405
    {"url": os.getenv("STAGING_URL", "https://backendeasy-staging.run.app"), "description": "Staging API"},
]

print("[STAGING] Staging settings loaded successfully")
print(f"[STAGING] DEBUG = {DEBUG}")
print(f"[STAGING] Database: {'PostgreSQL (Cloud SQL)' if database_url else 'SQLite (fallback)'}")
print(f"[STAGING] Cache: {'Redis' if _staging_redis_url else 'Dummy (no caching)'}")
print(f"[STAGING] Celery: {'Async (Redis broker)' if celery_broker else 'Synchronous (no broker)'}")
print("[STAGING] HTTPS: Not enforced (testing)")
print("[STAGING] CORS: Allow all origins")
