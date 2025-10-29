# STUB FILE - Will be removed when Firebase auth is implemented

from rest_framework_simplejwt.tokens import RefreshToken


def create_kiosk_token(kiosk_id):
    """Stub - will be replaced with Firebase"""
    refresh = RefreshToken()
    refresh["kiosk_id"] = kiosk_id
    refresh["type"] = "kiosk"
    return refresh
