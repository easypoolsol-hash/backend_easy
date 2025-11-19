import logging

from rest_framework.permissions import BasePermission

from bus_kiosk_backend.core.authentication import CloudTasksUser

logger = logging.getLogger(__name__)


class IsCloudTasksRequest(BasePermission):
    """
    Permission: Allow ONLY authenticated Cloud Tasks requests.

    Google Cloud IAM Pattern:
    - Cloud Run validates OIDC token (roles/run.invoker)
    - CloudTasksAuthentication identifies the request via headers
    - This permission explicitly allows Cloud Tasks users

    ALLOWED (Explicit):
    - Requests authenticated as CloudTasksUser

    DENIED (Everything Else):
    - Regular users (Firebase auth)
    - Kiosks
    - Unauthenticated requests
    - Any other case

    IAM Principle: Deny by default, grant explicitly for internal services.
    """

    def has_permission(self, request, view):
        # Check if authenticated as Cloud Tasks
        if not request.user or not request.user.is_authenticated:
            logger.warning("IsCloudTasksRequest: Not authenticated")
            return False

        # Check if it's a CloudTasksUser
        if not isinstance(request.user, CloudTasksUser):
            logger.warning(
                f"IsCloudTasksRequest DENIED: user type={type(request.user).__name__}, "
                f"expected=CloudTasksUser"
            )
            return False

        logger.debug(
            f"IsCloudTasksRequest ALLOWED: task={request.user.task_name}, "
            f"queue={request.user.queue_name}"
        )
        return True


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


class IsApprovedParent(BasePermission):
    """
    Permission: Allow ONLY approved parent users (deny-by-default IAM principle).

    Google-style architecture:
    - User is authentication layer (identity)
    - Parent is domain layer (authorization)
    - Approval status lives on Parent, not User

    Uses Django's built-in Groups and custom approval system.
    Deny-by-default means: If NOT an approved parent → Denied.

    ALLOWED (Explicit):
    - Authenticated users in "Parent" group
    - With linked Parent profile
    - With Parent.approval_status == "approved"

    DENIED (Everything Else):
    - Unauthenticated requests
    - Users without "Parent" group
    - Users without linked Parent profile
    - Users with Parent.approval_status == "pending" or "rejected"
    - Any other case

    IAM Principle: Deny by default, grant explicitly via approval.
    """

    def has_permission(self, request, view):
        # 1. Deny unauthenticated
        if not request.user or not request.user.is_authenticated:
            logger.warning("IsApprovedParent: User not authenticated")
            return False

        # 2. Check if user is in Parent group
        is_parent_group = request.user.groups.filter(name="Parent").exists()
        if not is_parent_group:
            logger.warning(f"IsApprovedParent DENIED: user={request.user.username} not in Parent group")
            return False

        # 3. Check linked Parent profile (domain entity)
        if not hasattr(request.user, "parent_profile") or not request.user.parent_profile:
            logger.warning(f"IsApprovedParent DENIED: user={request.user.username} has no linked Parent profile")
            return False

        # 4. Check approval status on Parent (authorization layer)
        parent = request.user.parent_profile
        if parent.approval_status != "approved":
            logger.warning(f"IsApprovedParent DENIED: user={request.user.username} parent_approval_status={parent.approval_status}")
            return False

        return True
