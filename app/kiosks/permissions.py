"""
Kiosk-specific permissions
"""

from rest_framework.permissions import BasePermission
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class IsKiosk(BasePermission):
    """
    Permission: Allow ONLY authenticated kiosk devices.

    ALLOWED:
    - Requests with valid JWT token containing type='kiosk'
    - Kiosk exists and is_active=True

    DENIED:
    - No token
    - Invalid/expired token
    - Token type != 'kiosk' (e.g., user tokens)
    - Kiosk not found or inactive
    """

    def has_permission(self, request, view):
        """Validate JWT token and verify it's a kiosk"""
        jwt_authenticator = JWTAuthentication()

        try:
            raw = jwt_authenticator.get_raw_token(jwt_authenticator.get_header(request))
            if raw is None:
                return False
            validated_token = jwt_authenticator.get_validated_token(raw)
        except (InvalidToken, AttributeError, TypeError):
            return False

        # Verify token type is 'kiosk'
        if validated_token.get("type") != "kiosk":
            return False

        # Extract and verify kiosk_id
        kiosk_id = validated_token.get("kiosk_id")
        if not kiosk_id:
            return False

        # Fetch active kiosk from database
        from kiosks.models import Kiosk

        try:
            kiosk = Kiosk.objects.select_related("bus").get(
                kiosk_id=kiosk_id, is_active=True
            )
        except Kiosk.DoesNotExist:
            return False

        # Store kiosk in request for view access
        request.kiosk = kiosk
        return True
