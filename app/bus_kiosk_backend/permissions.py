import logging

from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)


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
    Permission: Allow ONLY school administrators (deny-by-default IAM principle).

    Uses Django's built-in Groups (battery-included approach).
    Deny-by-default means: If NOT in "School Administrator" group → Denied.

    ALLOWED (Explicit):
    - Authenticated users in "School Administrator" group

    DENIED (Everything Else):
    - Unauthenticated requests
    - Kiosks (no groups)
    - Users in other groups (Parent, Backend Engineer, etc.)
    - Users without groups
    - Any other case

    IAM Principle: Deny by default, grant explicitly via groups.
    """

    def has_permission(self, request, view):
        # 1. Deny unauthenticated
        if not request.user or not request.user.is_authenticated:
            logger.warning("IsSchoolAdmin: User not authenticated")
            return False

        # 2. Allow ONLY users in "School Administrator" group
        # Uses Django's built-in permission system (battery-included)
        has_permission = request.user.groups.filter(name="School Administrator").exists()

        if not has_permission:
            user_groups = list(request.user.groups.values_list("name", flat=True))
            logger.warning(f"IsSchoolAdmin DENIED: user={request.user.username}, groups={user_groups}")

        return has_permission
