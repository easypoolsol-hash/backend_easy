"""
User Token Configuration

CRITICAL: This file defines token lifetimes for HUMAN USERS ONLY
- School Admins
- Parents
- Drivers

Kiosk tokens are configured separately in kiosks/token_config.py

Security Philosophy:
- Human users must re-authenticate frequently (maximum security)
- No long-term sessions (bank-level security)
- Stolen tokens expire quickly

SOLID Principle: Single Responsibility
This file is responsible ONLY for human user token configuration.
"""

from datetime import timedelta

from rest_framework_simplejwt.tokens import RefreshToken

# Token Lifetimes for Human Users
USER_ACCESS_TOKEN_LIFETIME = timedelta(minutes=15)  # Industry standard
USER_REFRESH_TOKEN_LIFETIME = timedelta(days=1)  # Must re-login daily (maximum security)


def create_user_token(user) -> RefreshToken:
    """
    Create JWT token for human user (school admin, parent, driver).

    EXPLICIT CONFIGURATION:
    - Access token: 15 minutes
    - Refresh token: 1 day
    - Token type: "user"
    - Contains: user_id claim

    Args:
        user: Django User instance

    Returns:
        RefreshToken with explicit user-specific settings

    Note:
        This function is ONLY for human users.
        Kiosks use kiosks.token_config.create_kiosk_token()
    """
    refresh = RefreshToken.for_user(user)

    # Explicit marker: This is a USER token
    refresh["type"] = "user"

    # Explicit lifetime: 1 day for human users (no global default)
    refresh.set_exp(lifetime=USER_REFRESH_TOKEN_LIFETIME)

    return refresh
