# STUB FILE - Kiosk permissions will be implemented with Firebase later

from rest_framework.permissions import BasePermission


class IsKiosk(BasePermission):
    """Stub permission - allows all authenticated requests for now"""

    def has_permission(self, request, view):
        # For now, allow any authenticated user
        # Will be replaced with proper Firebase device auth
        return request.user and request.user.is_authenticated
