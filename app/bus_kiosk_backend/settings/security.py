"""
Security settings module.
Centralized security configuration following Fortune 500 best practices.

This module contains all security-related settings that are then
imported and customized by environment-specific settings.
"""

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

# Password validation - Already defined in base.py
# Override here if needed for specific environments

# Security middleware
# Note: This is a reference - actual MIDDLEWARE is in base.py
SECURITY_MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
]

print("[SECURITY] Security settings module loaded")
