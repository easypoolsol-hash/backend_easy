# STUB FILE - Kiosk authentication will be implemented with Firebase later
# For now, kiosk endpoints are accessible without authentication

from rest_framework_simplejwt.authentication import JWTAuthentication


class KioskJWTAuthentication(JWTAuthentication):
    """Stub - will be replaced with Firebase auth"""

    pass


def activate_kiosk(kiosk_id, activation_token):
    """Stub - will be implemented later"""
    raise NotImplementedError("Kiosk activation will be implemented with Firebase")
