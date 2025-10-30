"""
Security settings module.
Centralized security configuration following Fortune 500 best practices.

This module contains all security-related settings that are then
imported and customized by environment-specific settings.
"""

from typing import Any

# Security headers and HTTPS enforcement
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Session security
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 1209600  # 2 weeks

# CSRF protection
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_USE_SESSIONS = False  # Use cookies for CSRF tokens

# Password validation
AUTH_PASSWORD_VALIDATORS: list[dict[str, Any]] = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 8,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Security middleware
# Note: This is a reference - actual MIDDLEWARE is in base.py
SECURITY_MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
]

print("[SECURITY] Security settings module loaded")
