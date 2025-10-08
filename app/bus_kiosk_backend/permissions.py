from rest_framework.permissions import BasePermission


class DenyByDefault(BasePermission):
    """
    AWS-style deny-by-default permission.

    Denies ALL access unless view explicitly overrides with specific permissions.
    Forces developers to consciously choose permissions for each endpoint.

    Pattern:
    - Global default: DenyByDefault (this class)
    - Each view must explicitly declare: permission_classes = [IsKiosk] or [IsSchoolAdmin] or [AllowAny]
    - Forget to declare? → Access denied (secure by default)

    Usage in settings.py:
        REST_FRAMEWORK = {
            'DEFAULT_PERMISSION_CLASSES': [
                'bus_kiosk_backend.permissions.DenyByDefault',
            ],
        }
    """

    def has_permission(self, request, view):
        """Deny all access - views must override with explicit permissions"""
        return False


class IsSchoolAdmin(BasePermission):
    """
    Permission: Allow ONLY school administrators (deny-by-default).

    Deny-by-default means: If NOT school_admin → Denied (including kiosks).

    ALLOWED (Explicit):
    - Authenticated User objects with role.name='school_admin'

    DENIED (Everything Else):
    - Unauthenticated requests
    - Kiosks (don't have User.role.name=='school_admin')
    - Users with other roles (parent, teacher, etc.)
    - Users without role attribute
    - Any other case

    No need to explicitly check "is kiosk?" because kiosks don't have
    role=='school_admin', so they're automatically denied.
    """

    def has_permission(self, request, view):
        # 1. Deny unauthenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # 2. Deny if no role attribute
        if not hasattr(request.user, "role") or not request.user.role:
            return False

        # 3. Allow ONLY school_admin role
        # Everything else (kiosks, parents, teachers, etc.) is denied here
        return request.user.role.name == "school_admin"
