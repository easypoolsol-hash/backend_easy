"""
Kiosk Token Configuration

CRITICAL: This file defines token lifetimes for KIOSK DEVICES ONLY
- Physical kiosk devices at school gates
- Autonomous operation during holidays
- No human to re-authenticate

User tokens are configured separately in users/token_config.py

Security Philosophy:
- Kiosk devices operate autonomously (long-term tokens)
- Physical device security (controlled location)
- 60-day lifetime for 2-month holiday periods

SOLID Principle: Single Responsibility
This file is responsible ONLY for kiosk device token configuration.
"""

from datetime import timedelta

from rest_framework_simplejwt.tokens import RefreshToken

# Token Lifetimes for Kiosk Devices (IoT)
KIOSK_ACCESS_TOKEN_LIFETIME = timedelta(minutes=15)  # Industry standard
KIOSK_REFRESH_TOKEN_LIFETIME = timedelta(days=60)  # Autonomous operation (2-month holidays)


def create_kiosk_token(kiosk_id: str) -> RefreshToken:
    """
    Create JWT token for kiosk device (autonomous IoT).

    EXPLICIT CONFIGURATION:
    - Access token: 15 minutes
    - Refresh token: 60 days
    - Token type: "kiosk"
    - Contains: kiosk_id claim

    Args:
        kiosk_id: Unique kiosk identifier (e.g., "KIOSK-SCHOOL-001")

    Returns:
        RefreshToken with explicit kiosk-specific settings

    Note:
        This function is ONLY for kiosk devices.
        Human users use users.token_config.create_user_token()
    """
    refresh = RefreshToken()

    # Explicit marker: This is a KIOSK token
    refresh["kiosk_id"] = kiosk_id
    refresh["type"] = "kiosk"

    # Explicit lifetime: 60 days for autonomous kiosk operation (no global default)
    refresh.set_exp(lifetime=KIOSK_REFRESH_TOKEN_LIFETIME)

    return refresh
