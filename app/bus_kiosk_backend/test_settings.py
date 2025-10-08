"""
Test settings for Django project.
Uses SQLite for faster testing instead of PostgreSQL.
"""

from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Import necessary settings from main settings
SECRET_KEY = "test-secret-key"
DEBUG = True
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "corsheaders",
    "django_filters",
    # Local apps
    "users",
    "students",
    "buses",
    "events",
    "kiosks",
]

AUTH_USER_MODEL = "users.User"

# Override database configuration for tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",  # Use in-memory database for tests
    }
}

# Allowed hosts for testing
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

# Basic middleware for tests - minimal set (NO CSRF for API testing)
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # Removed CSRF middleware - APIs use token auth, not session + CSRF
    # Removed AuthenticationMiddleware for tests
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "bus_kiosk_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

# Use faster password hasher for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# REST Framework settings for tests - OVERRIDE global authentication
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],  # No global authentication for tests
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

# Encryption key for PII data (test key)
ENCRYPTION_KEY = "NktQAERTtbDEW5ZiIWXy8BEpOVzUWhrTc7elWaaYIY0="

# Debug print to verify settings are loaded
print("TEST SETTINGS LOADED - REST_FRAMEWORK:", REST_FRAMEWORK)

# Avoid accessing django.apps at import time without guards. In some CI
# environments a shadowed or incomplete `django` module can cause
# AttributeError: module 'django' has no attribute 'apps'. Use a safe
# import/getattr pattern so tests don't crash at import time.
from typing import Any

try:
    # Try to import the apps registry the normal way. This will fail
    # cleanly if Django isn't properly installed or if a local module
    # is shadowing the real package.
    from django.apps import apps as _django_apps_module
except Exception:  # pragma: no cover - defensive for CI
    django_apps: Any | None = None

if getattr(_django_apps_module, "ready", False):
    from django.conf import settings

    print("RUNTIME REST_FRAMEWORK:", settings.REST_FRAMEWORK)

# Disable Celery during tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Disable caching during tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    },
    "api_cache": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    },
}

# Basic logging for tests
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
        "level": "WARNING",
    },
}

# Fix media URL for tests (don't serve all URLs as media files!)
MEDIA_URL = "/media/"
