from rest_framework.permissions import BasePermission, DjangoModelPermissions


class IsKiosk(BasePermission):
    """
    Custom permission to only allow kiosk devices to access certain endpoints.
    Kiosks authenticate using API key in header.
    """

    def has_permission(self, request, view):
        # Check for kiosk API key in header
        api_key = request.headers.get('X-Kiosk-API-Key')
        if not api_key:
            return False

        # In a real implementation, you'd validate the API key against the database
        # For now, we'll just check if it exists
        from kiosks.models import Kiosk
        try:
            kiosk = Kiosk.objects.get(api_key_hash=api_key)
            # Store kiosk in request for use in views
            request.kiosk = kiosk
            return True
        except Kiosk.DoesNotExist:
            return False


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
        if hasattr(request.user, 'role') and request.user.role.name == 'school_admin':
            return True

        # Alternative: Check Django permissions
        # return request.user.has_perm('kiosks.change_kiosk') or request.user.has_perm('kiosks.delete_kiosk')

        return False
