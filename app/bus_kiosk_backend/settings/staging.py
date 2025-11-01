"""
Staging settings.
Production mirror for testing before production deployment.

Fortune 500 Pattern:
- Inherits ALL production settings
- Overrides ONLY what differs from production
- Uses same PostgreSQL, same security, same config
- This ensures staging matches production (config parity)

The goal: If it works in staging, it WILL work in production.
"""

import os

# Import ALL production settings (staging = production mirror)
from .production import *  # noqa: F403

# Override: Environment identifier
ENVIRONMENT = "staging"

# Override: DEBUG can be enabled for troubleshooting (production is False)
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# Override: Allowed hosts (staging-specific domains)
_allowed_hosts_env = os.getenv("ALLOWED_HOSTS", ".run.app")
ALLOWED_HOSTS = _allowed_hosts_env.split(",")

# Override: CORS origins (staging-specific)
_cors_origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
if _cors_origins_env:
    CORS_ALLOWED_ORIGINS = _cors_origins_env.split(",")
else:
    # Default: Allow staging frontend
    CORS_ALLOWED_ORIGINS = [
        "https://stage.easypool.in",
        "https://easypool-30af3--staging-*.web.app",
    ]

# Override: CSRF trusted origins (staging-specific)
_csrf_origins_env = os.getenv("CSRF_TRUSTED_ORIGINS", "")
if _csrf_origins_env:
    CSRF_TRUSTED_ORIGINS = _csrf_origins_env.split(",")
else:
    # Default: Trust staging domains
    CSRF_TRUSTED_ORIGINS = [
        "https://stage.easypool.in",
        "https://easypool-backend-staging-*.run.app",
    ]

# Override: Relaxed HSTS for staging (production has 1 year)
SECURE_HSTS_SECONDS = 3600  # 1 hour
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# Override: More verbose logging for staging (production is WARNING)
LOGGING["root"]["level"] = "INFO"  # noqa: F405  # type: ignore[index]
LOGGING["loggers"]["django"]["level"] = "INFO"  # noqa: F405  # type: ignore[index]
LOGGING["loggers"]["bus_kiosk_backend"]["level"] = "DEBUG"  # noqa: F405  # type: ignore[index]

# Override: Keep DRF Browsable API for staging testing (production disables it)
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [  # noqa: F405
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",  # Keep for staging
]

# Override: API docs show staging server
SPECTACULAR_SETTINGS["SERVERS"] = [  # noqa: F405
    {"url": os.getenv("STAGING_URL", "https://easypool-backend-staging.run.app"), "description": "Staging API"},
]

# Everything else (DATABASE, SECRETS, CACHE, CELERY, SECURITY) inherits from production.py

print("[STAGING] Staging settings loaded successfully (inherits from production)")
print(f"[STAGING] DEBUG = {DEBUG}")
print("[STAGING] Database: Inherited from production (PostgreSQL)")
print("[STAGING] Cache: Inherited from production (Redis or in-memory)")
print("[STAGING] Security: Inherited from production (relaxed HSTS)")
print("[STAGING] All other settings: Same as production")
