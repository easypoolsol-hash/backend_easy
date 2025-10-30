"""
Kiosk Authentication Module

Provides JWT-based authentication for kiosk devices.
Supports both access tokens and refresh tokens with rotation.
"""

from hashlib import sha256
import hmac

from django.conf import settings
from django.utils import timezone
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Kiosk, KioskActivationToken


class KioskJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication for kiosk devices.

    Supports kiosk-specific JWT tokens with kiosk_id claim.
    Validates kiosk is active and exists.
    """

    def get_user(self, validated_token):
        """
        Get the kiosk user object from JWT token.

        Override to return Kiosk object instead of User object.
        """
        try:
            kiosk_id = validated_token["kiosk_id"]
        except KeyError:
            raise exceptions.AuthenticationFailed("Token missing kiosk_id claim") from None

        try:
            kiosk = Kiosk.objects.get(kiosk_id=kiosk_id)
        except Kiosk.DoesNotExist:
            raise exceptions.AuthenticationFailed("Kiosk not found") from None

        # Check if kiosk is active
        if not kiosk.is_active:
            raise exceptions.AuthenticationFailed("Kiosk is deactivated")

        return kiosk

    def authenticate(self, request):
        """
        Authenticate the request using JWT token.

        Returns (kiosk, token) tuple if authentication succeeds.
        """
        # Get token from header
        header = self.get_header(request)
        if header is None:
            return None

        # Decode token
        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        # Validate token
        validated_token = self.get_validated_token(raw_token)

        # Get kiosk from token
        kiosk = self.get_user(validated_token)

        return (kiosk, validated_token)


def activate_kiosk(kiosk_id, activation_token):
    """
    Activate a kiosk using one-time activation token.

    Args:
        kiosk_id (str): Kiosk identifier
        activation_token (str): One-time activation token

    Returns:
        dict: {
            'refresh_token': str,
            'access_token': str,
            'kiosk': Kiosk,
            'message': str
        }

    Raises:
        ValueError: If activation fails
    """
    try:
        # Find kiosk
        kiosk = Kiosk.objects.get(kiosk_id=kiosk_id)
    except Kiosk.DoesNotExist:
        raise ValueError("Invalid kiosk_id") from None

    # Hash submitted token
    submitted_hash = hmac.new(settings.SECRET_KEY.encode(), activation_token.encode(), sha256).hexdigest()

    try:
        activation = KioskActivationToken.objects.get(kiosk=kiosk, token_hash=submitted_hash, is_used=False)
    except KioskActivationToken.DoesNotExist:
        raise ValueError("Invalid or already used activation token") from None

    # Validate token
    if not activation.is_valid():
        raise ValueError("Activation token expired")

    # ✅ ACTIVATE KIOSK (One-time action)
    activation.is_used = True
    activation.used_at = timezone.now()
    activation.save()

    kiosk.is_active = True
    kiosk.save()

    # Generate JWT tokens (60-day refresh + 15-min access)
    refresh = RefreshToken()
    refresh["kiosk_id"] = kiosk.kiosk_id
    refresh["type"] = "kiosk"

    return {
        "refresh_token": str(refresh),
        "access_token": str(refresh.access_token),
        "kiosk": kiosk,
        "message": "Kiosk activated successfully. Token is now invalid.",
    }


class KioskJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """OpenAPI schema extension for KioskJWTAuthentication"""

    target_class = "kiosks.authentication.KioskJWTAuthentication"
    name = "KioskJWTAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT auth for kiosk devices. Use: Bearer <token>",
        }
