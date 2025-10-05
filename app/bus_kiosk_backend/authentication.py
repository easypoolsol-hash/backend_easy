"""
Custom authentication classes (Fortune 500 pattern)

Extends DRF's authentication framework for device authentication.
Uses official SimpleJWT extension pattern for security.
"""

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class KioskJWTAuthentication(JWTAuthentication):
    """
    JWT authentication for kiosk devices (Fortune 500 pattern)

    Extends SimpleJWT's secure authentication to support kiosk devices.
    All security features (signature validation, expiry, blacklist) inherited.

    Security guarantees:
    - Token signature validated by parent class
    - Token expiry checked by parent class
    - Token type isolation (kiosk vs user tokens)
    - Active status verification
    - No custom cryptography (uses proven SimpleJWT)

    Usage:
        @authentication_classes([KioskJWTAuthentication])
        @permission_classes([IsAuthenticated])
        def kiosk_heartbeat(request):
            kiosk = request.user  # Authenticated kiosk object

    Official pattern from SimpleJWT documentation:
    https://django-rest-framework-simplejwt.readthedocs.io/
    """

    def get_user(self, validated_token):
        """
        Override to return Kiosk instead of User.

        At this point, the token is already validated by parent class:
        - Signature verified ✓
        - Expiry checked ✓
        - Structure validated ✓

        We only change WHAT object to return (Kiosk vs User).

        Args:
            validated_token: Already validated JWT token payload

        Returns:
            Kiosk object if valid kiosk token, None otherwise

        Security checks:
            1. Token type must be 'kiosk' (prevents user tokens)
            2. kiosk_id must be present
            3. Kiosk must exist in database
            4. Kiosk must be active (is_active=True)
        """
        # Security check 1: Verify token type
        token_type = validated_token.get('type')
        if token_type != 'kiosk':
            # Not a kiosk token (might be user token)
            # Return None -> DRF will return 401 Unauthorized
            return None

        # Security check 2: Extract kiosk_id
        kiosk_id = validated_token.get('kiosk_id')
        if not kiosk_id:
            # Token missing kiosk_id (malformed)
            return None

        # Security check 3 & 4: Fetch active kiosk from database
        from kiosks.models import Kiosk

        try:
            kiosk = Kiosk.objects.select_related('bus').get(
                kiosk_id=kiosk_id,
                is_active=True  # CRITICAL: Only active kiosks
            )
            return kiosk
        except Kiosk.DoesNotExist:
            # Kiosk not found or inactive
            # Return None -> DRF will return 401 Unauthorized
            return None

    def authenticate(self, request):
        """
        Override to return None for non-kiosk tokens.

        This ensures user tokens don't authenticate with this class.
        DRF will return 401 if this is the only authentication class.
        """
        try:
            # Get validated token using parent class
            header = self.get_header(request)
            if header is None:
                return None

            raw_token = self.get_raw_token(header)
            if raw_token is None:
                return None

            validated_token = self.get_validated_token(raw_token)

            # Check if it's a kiosk token BEFORE calling get_user
            if validated_token.get('type') != 'kiosk':
                # Not a kiosk token - return None (authentication fails)
                return None

            # It's a kiosk token - get the kiosk object
            user = self.get_user(validated_token)
            if user is None:
                return None

            return (user, validated_token)

        except InvalidToken:
            # Token invalid, expired, or malformed
            # Return None (authentication fails, DRF returns 401)
            return None
