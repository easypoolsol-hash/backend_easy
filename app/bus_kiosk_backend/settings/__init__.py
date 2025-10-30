"""
Settings package initialization with automatic environment detection.

Fortune 500 Pattern (12-Factor App):
- Auto-detects environment from DJANGO_ENV variable
- Falls back to intelligent detection (GITHUB_ACTIONS, GAE_APPLICATION, etc.)
- Loads appropriate settings module (local, ci, production)
- NO manual settings file specification needed

Environment Detection Priority:
1. DJANGO_ENV environment variable (explicit override)
2. GITHUB_ACTIONS=true → ci
3. GAE_APPLICATION exists → production (Google App Engine)
4. K_SERVICE exists → production (Google Cloud Run)
5. Default → local (development)

Usage:
    # In manage.py, wsgi.py, asgi.py:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bus_kiosk_backend.settings")

    # To override environment:
    export DJANGO_ENV=production  # Force production settings
    export DJANGO_ENV=local       # Force local settings
    export DJANGO_ENV=ci          # Force CI settings
"""

import os
import sys


# Detect environment
def get_environment() -> str:
    """
    Auto-detect the current environment.

    Returns:
        str: Environment name ('local', 'ci', or 'production')
    """
    # 1. Explicit override via DJANGO_ENV
    django_env = os.getenv("DJANGO_ENV", "").lower()
    if django_env in ("local", "ci", "staging", "production"):
        return django_env

    # 2. CI/CD detection
    if os.getenv("GITHUB_ACTIONS") == "true":
        return "ci"
    if os.getenv("GITLAB_CI") == "true":
        return "ci"
    if os.getenv("CIRCLECI") == "true":
        return "ci"
    if os.getenv("CI") == "true":
        return "ci"

    # 3. Production platform detection
    if os.getenv("GAE_APPLICATION"):  # Google App Engine
        return "production"
    if os.getenv("K_SERVICE"):  # Google Cloud Run
        return "production"
    if os.getenv("AWS_EXECUTION_ENV"):  # AWS Lambda / ECS
        return "production"
    if os.getenv("KUBERNETES_SERVICE_HOST"):  # Kubernetes
        return "production"

    # 4. Default to local development
    return "local"


# Auto-detect and load appropriate settings
environment = get_environment()

# Import the appropriate settings module
if environment == "production":
    from .production import *  # noqa: F403

    print("[SETTINGS] Loaded PRODUCTION settings")
elif environment == "staging":
    from .staging import *  # noqa: F403

    print("[SETTINGS] Loaded STAGING settings")
elif environment == "ci":
    from .ci import *  # noqa: F403

    print("[SETTINGS] Loaded CI settings")
else:  # local
    from .local import *  # noqa: F403

    print("[SETTINGS] Loaded LOCAL settings")

# Export environment for runtime introspection
ENVIRONMENT = environment

print(f"[SETTINGS] Auto-detected environment: {environment.upper()}")
print(f"[SETTINGS] Settings module: bus_kiosk_backend.settings.{environment}")
print("[SETTINGS] Override with: export DJANGO_ENV=<local|ci|staging|production>")
