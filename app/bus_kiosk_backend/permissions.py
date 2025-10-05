from rest_framework.permissions import BasePermission
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class IsKiosk(BasePermission):
    """
    Custom permission to only allow authenticated kiosk devices.

    Fortune 500 Security Pattern:
    - JWT token-based authentication (not raw API keys in headers)
    - Validates token signature and expiry
    - Checks token type is 'kiosk'
    - Verifies kiosk is still active
    - Stores kiosk object in request for view access

    Usage:
    1. Kiosk authenticates: POST /api/kiosks/auth/ {kiosk_id, api_key}
    2. Gets JWT token in response
    3. Includes token in header: Authorization: Bearer <token>
    4. This permission validates the token
    """

    def has_permission(self, request, view):
        """
        Validate JWT token and extract kiosk information

        Security checks:
        1. Token exists and is valid
        2. Token type is 'kiosk' (not user token)
        3. Kiosk exists in database
        4. Kiosk is active
        """
        # Authenticate using JWT
        jwt_authenticator = JWTAuthentication()

        try:
            # Validate token and get payload
            validated_token = jwt_authenticator.get_validated_token(
                jwt_authenticator.get_raw_token(
                    jwt_authenticator.get_header(request)
                )
            )
        except (InvalidToken, AttributeError, TypeError):
            # Token missing, invalid, or expired
            return False

        # Verify token type is 'kiosk' (not a user token)
        token_type = validated_token.get('type')
        if token_type != 'kiosk':
            return False

        # Extract kiosk_id from token
        kiosk_id = validated_token.get('kiosk_id')
        if not kiosk_id:
            return False

        # Fetch kiosk from database
        from kiosks.models import Kiosk

        try:
            kiosk = Kiosk.objects.select_related('bus').get(
                kiosk_id=kiosk_id,
                is_active=True  # CRITICAL: Only allow active kiosks
            )
        except Kiosk.DoesNotExist:
            # Kiosk not found or inactive
            return False

        # Store kiosk in request for view access
        request.kiosk = kiosk

        return True


class IsSchoolAdmin(BasePermission):
    """
    Permission that allows access to school administrators.
    Uses Django's permission system combined with role checking.
    """

    def has_permission(self, request, view):
        # Must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # Check role-based access (your custom role system)
        if hasattr(request.user, "role") and request.user.role.name == "school_admin":
            return True

        # Alternative: Check Django permissions
        # return request.user.has_perm('kiosks.change_kiosk') or \
        #        request.user.has_perm('kiosks.delete_kiosk')

        return False
