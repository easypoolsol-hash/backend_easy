"""
Base settings for bus_kiosk_backend project.
Contains common settings shared across all environments.
Environment-specific settings inherit from this file.
"""

from datetime import timedelta
import os
from pathlib import Path
from typing import Any

# Firebase Admin SDK initialization for Frontend Easy authentication
# NOTE: Firebase initialization is deferred to environment-specific settings
# Production: Injected via Google Secret Manager
# Local: Loaded in local.py via .env
# Firebase initialization - done in environment-specific settings
# Local: local.py reads from file
# Production/Staging: production.py/staging.py read from Secret Manager

# 12-Factor App Pattern: NO .env loading in base settings
# - Production: Environment variables injected by container orchestration (GCP Secret Manager, K8s secrets)
# - Local Development: .env loaded in local.py only
# - CI/CD: Environment variables set in CI pipeline
# This follows Fortune 500 best practices: Never commit secrets, never use .env in production

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Logging configuration - Environment-based (12-factor app pattern)
# CI/Docker: Set USE_FILE_LOGGING=false for console-only logging
# Production: Leave default (true) for file logging
USE_FILE_LOGGING = os.getenv("USE_FILE_LOGGING", "false").lower() == "true"

# Create logs directory only if file logging is enabled
if USE_FILE_LOGGING:
    LOGS_DIR = BASE_DIR / "logs"
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


# Security keys - Must be overridden in environment-specific settings
# - Local: Set by make backend-fresh (backend_fresh.bat) or loaded from .env
# - Production: Injected by Google Secret Manager
# - CI/mypy: Uses ci.py settings
# - Fallback for imports: Use a dummy key (will be overridden by environment settings)
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-FALLBACK-KEY-DO-NOT-USE-IN-PRODUCTION-only-for-imports",
)

# Encryption key for PII data
# Generate using: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY = os.getenv(
    "ENCRYPTION_KEY",
    "dKWpt_QqCynKj9NhnY6Fs7cbLd-itxLzGOfbcTwTJtM=",  # Test key from test_settings.py
)

# Debug mode - Default to False for safety (overridden in environment settings)
DEBUG = False

# Allowed hosts - Base configuration (extended in environment settings)
ALLOWED_HOSTS: list[str] = [
    "easypool.in",
    "www.easypool.in",
    "api.easypool.in",
]

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "channels",  # Django Channels for WebSocket support
    "rest_framework",
    "drf_spectacular",  # OpenAPI schema generation
    "drf_spectacular_sidecar",  # Self-hosted Swagger UI assets
    "corsheaders",  # CORS handling
    "django_prometheus",  # Metrics collection
    "drf_api_logger",  # API request logging
    "django_filters",  # Advanced filtering
    "django_celery_beat",  # Periodic tasks
    "django_celery_results",  # Task results storage
    "django_redis",  # Redis cache backend
    # Local apps
    "users",
    "students",
    "buses",
    "events",
    "kiosks",
    "realtime",  # Real-time WebSocket communication
    "notifications",  # Push notifications for parents
]

# Custom user model
AUTH_USER_MODEL = "users.User"

# REST Framework configuration
REST_FRAMEWORK: dict[str, Any] = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # Cloud Tasks auth must be first - handles GCP internal requests
        "bus_kiosk_backend.core.authentication.CloudTasksAuthentication",
        "bus_kiosk_backend.core.authentication.FirebaseAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "bus_kiosk_backend.permissions.DenyByDefault",  # AWS-style: Deny unless explicitly allowed
    ],
    "DEFAULT_PAGINATION_CLASS": ("rest_framework.pagination.PageNumberPagination"),
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
        "login": "5/minute",
        "register": "3/minute",
        "upload": "10/minute",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "EXCEPTION_HANDLER": "bus_kiosk_backend.exceptions.custom_exception_handler",
    # Timezone: Return datetimes in Asia/Kolkata (IST) instead of UTC
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%S.%f%z",  # ISO 8601 with timezone
}

# Celery Configuration
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
# Store results in Django database for visibility in admin panel
CELERY_RESULT_BACKEND = "django-db"  # Uses django_celery_results app
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Kolkata"  # Match Django timezone (IST)
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000
CELERY_WORKER_CONCURRENCY = 4

# Celery Results - Keep for debugging and monitoring
CELERY_RESULT_EXPIRES = 86400  # Keep results for 24 hours (86400 seconds)

# Celery Task Routing - Route ML tasks to dedicated ML queue
CELERY_TASK_ROUTES = {
    "students.tasks.process_student_photo_embedding_task": {"queue": "ml_tasks"},
    # Other tasks go to default queue
}

# Celery Beat Settings
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Django Channels Configuration (WebSocket Support)
ASGI_APPLICATION = "bus_kiosk_backend.asgi.application"

# Channel Layers - Configured per environment
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# Logging Configuration - Build handlers dynamically
_log_handlers: dict[str, dict[str, Any]] = {
    "console": {
        "class": "logging.StreamHandler",
        "formatter": "verbose",
    },
}

# Add file handlers only if file logging is enabled
if USE_FILE_LOGGING:
    _log_handlers["file"] = {
        "class": "logging.handlers.RotatingFileHandler",
        "filename": str(LOGS_DIR / "django.log"),
        "maxBytes": 1024 * 1024 * 10,  # 10MB
        "backupCount": 5,
        "formatter": "json",
    }
    _log_handlers["api_file"] = {
        "class": "logging.handlers.RotatingFileHandler",
        "filename": str(LOGS_DIR / "api.log"),
        "maxBytes": 1024 * 1024 * 10,  # 10MB
        "backupCount": 5,
        "formatter": "json",
    }

# Determine handler names for loggers
_default_handlers = ["console", "file"] if USE_FILE_LOGGING else ["console"]
_api_handlers = ["api_file"] if USE_FILE_LOGGING else ["console"]

LOGGING: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "json": {
            "format": (
                '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
                '"logger": "%(name)s", "message": "%(message)s", '
                '"module": "%(module)s", "function": "%(funcName)s", '
                '"line": %(lineno)d}'
            ),
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
        },
    },
    "handlers": _log_handlers,
    "root": {
        "handlers": _default_handlers,
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": _default_handlers,
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": _default_handlers,
            "level": "WARNING",
            "propagate": False,
        },
        "bus_kiosk_backend": {
            "handlers": _default_handlers,
            "level": "INFO",
            "propagate": False,
        },
        "drf_api_logger": {
            "handlers": _api_handlers,
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Security Settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# CORS Settings - Base configuration (extended in environment settings)
CORS_ALLOWED_ORIGINS = [
    "https://easypool.in",
    "https://www.easypool.in",
    "https://api.easypool.in",
]
CORS_ALLOW_CREDENTIALS = True

# CSRF trusted origins for HTTPS
CSRF_TRUSTED_ORIGINS = [
    "https://easypool.in",
    "https://www.easypool.in",
    "https://api.easypool.in",
]

# DRF Spectacular settings
SPECTACULAR_SETTINGS: dict[str, Any] = {
    "TITLE": "Bus Kiosk Backend API",
    "DESCRIPTION": "Industrial REST API for Bus Kiosk face recognition system",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "PREPROCESSING_HOOKS": [
        "bus_kiosk_backend.schema_hooks.exclude_health_endpoints",
    ],
    "POSTPROCESSING_HOOKS": [
        "bus_kiosk_backend.schema_hooks.mark_activation_public",
        "bus_kiosk_backend.schema_hooks.remove_nullable_from_required",
    ],
    "SERVERS": [
        {"url": "https://api.easypool.in", "description": "Production API"},
    ],
    "SECURITY": [{"Bearer": []}],
    "SECURITY_SCHEMES": {
        "Bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "Firebase ID Token",
            "description": ("Firebase ID Token authorization header using the Bearer scheme. Example: 'Authorization: Bearer {firebase_token}'"),
        }
    },
    # Self-hosted Swagger UI (no CDN)
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    # Google Way: Split request/response schemas for proper nullable handling
    "COMPONENT_SPLIT_REQUEST": True,
}

# OpenAPI Validation Settings
OPENAPI_VALIDATE_REQUESTS = True
OPENAPI_VALIDATE_RESPONSES = True
OPENAPI_FAIL_ON_ERROR = False

# Middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # WhiteNoise for static files
    "corsheaders.middleware.CorsMiddleware",
    "bus_kiosk_backend.middleware.SecurityHeadersMiddleware",
    "bus_kiosk_backend.middleware.openapi_validation.OpenAPIValidationMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "bus_kiosk_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "bus_kiosk_backend.wsgi.application"

# Database - Configured per environment
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Cache configuration - Configured per environment
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
        "KEY_PREFIX": "bus_kiosk",
        "TIMEOUT": 300,
    },
    "api_cache": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "api-cache",
        "KEY_PREFIX": "api",
        "TIMEOUT": 3600,
    },
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": ("django.contrib.auth.password_validation.UserAttributeSimilarityValidator"),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"  # IST (UTC+5:30) - All operations in India
USE_I18N = True
USE_TZ = True  # Keep timezone-aware (stores with timezone info)

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media files (User uploads - student photos, etc.)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Google Maps API Key
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

# Firebase Admin SDK - Common initialization for all environments
# Initialized once here, all environments inherit it
try:
    import json

    import firebase_admin
    from firebase_admin import credentials

    _firebase_key = os.environ.get("FIREBASE_SERVICE_ACCOUNT_KEY")
    if _firebase_key and not firebase_admin._apps:
        cred = credentials.Certificate(json.loads(_firebase_key))
        firebase_admin.initialize_app(cred)
        print("[FIREBASE] Firebase Admin initialized successfully")
except (ImportError, ValueError, KeyError) as e:
    print(f"[FIREBASE] Firebase initialization skipped: {e}")
    pass  # Firebase optional in local/CI environments

# Google Cloud Tasks Configuration for async notifications
# These are overridden in environment-specific settings
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "easypool-backend")
GCP_REGION = os.getenv("GCP_REGION", "asia-south1")

# Cloud Tasks queue name (environment-specific)
CLOUD_TASKS_QUEUE_NAME = os.getenv("CLOUD_TASKS_QUEUE_NAME", "notifications-queue-dev")

# Service account for Cloud Tasks to invoke Cloud Run
CLOUD_TASKS_SERVICE_ACCOUNT = os.getenv("CLOUD_TASKS_SERVICE_ACCOUNT", "easypool-cloud-run-sa@easypool-backend.iam.gserviceaccount.com")

# Backend URL for Cloud Tasks callbacks
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Face Enrollment Configuration
# Configurable settings for parent face enrollment (auto-capture mode)
# Parents use camera to scan student face - app auto-captures multiple photos
# These settings control how many photos are captured per enrollment session
FACE_ENROLLMENT_MIN_PHOTOS = int(os.getenv("FACE_ENROLLMENT_MIN_PHOTOS", "3"))
FACE_ENROLLMENT_MAX_PHOTOS = int(os.getenv("FACE_ENROLLMENT_MAX_PHOTOS", "5"))
FACE_ENROLLMENT_PHOTO_MAX_SIZE_MB = int(os.getenv("FACE_ENROLLMENT_PHOTO_MAX_SIZE_MB", "5"))
