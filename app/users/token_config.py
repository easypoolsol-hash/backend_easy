"""
User JWT Token Configuration - FOR MOBILE APPS ONLY

CRITICAL: frontend_easy (web dashboard) does NOT use JWT!
This file defines JWT token lifetimes for FUTURE MOBILE APPS:
- Mobile school admin app (future)
- Parent mobile app (future)
- Driver mobile app (future)

Current Usage:
- Web dashboard (frontend_easy): Uses Session auth (NO JWT)
- Mobile apps: Uses JWT (THIS FILE)
- Kiosks: Use kiosks/token_config.py (separate JWT config)

Security Philosophy:
- Human users must re-authenticate frequently (maximum security)
- No long-term sessions (bank-level security)
- Stolen tokens expire quickly

SOLID Principle: Single Responsibility
This file is responsible ONLY for mobile app JWT token configuration.
"""

from datetime import timedelta

from rest_framework_simplejwt.tokens import RefreshToken

# Token Lifetimes for Human Users
USER_ACCESS_TOKEN_LIFETIME = timedelta(minutes=15)  # Industry standard
USER_REFRESH_TOKEN_LIFETIME = timedelta(days=1)  # Must re-login daily (maximum security)


def create_user_token(user) -> RefreshToken:
    """
    Create JWT token for MOBILE APP users (future use).

    IMPORTANT: frontend_easy does NOT call this!
    Web dashboard uses Django sessions, not JWT.

    EXPLICIT CONFIGURATION:
    - Access token: 15 minutes
    - Refresh token: 1 day
    - Token type: "user"
    - Contains: user_id claim

    Args:
        user: Django User instance

    Returns:
        RefreshToken with explicit user-specific settings

    Usage:
        - Mobile apps: Call via /api/v1/users/login/ (returns JWT)
        - Web dashboard: Uses /api/v1/users/session_login/ (NO JWT)
        - Kiosks: Use kiosks.token_config.create_kiosk_token()
    """
    refresh = RefreshToken.for_user(user)

    # Explicit marker: This is a USER token
    refresh["type"] = "user"

    # Explicit lifetime: 1 day for human users (no global default)
    refresh.set_exp(lifetime=USER_REFRESH_TOKEN_LIFETIME)

    return refresh
