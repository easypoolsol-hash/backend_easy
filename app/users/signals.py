"""
User-related signals for last login tracking and audit logging.

Industry Standard Pattern (Django Signals):
- Centralized login tracking across all authentication methods
- Automatic last_login update without code duplication
- Decoupled from authentication backends
- Works with Firebase, sessions, WebSockets, etc.
- Comprehensive audit trail for compliance (7-year retention)

Usage:
    Signal is automatically connected via apps.py
    No manual code needed in auth backends
"""

import logging

from django.contrib.auth.signals import user_logged_in
from django.dispatch import Signal, receiver
from django.utils import timezone

logger = logging.getLogger(__name__)

# Custom signal for Firebase/WebSocket authentication
# (they don't use Django's session login, so we need a custom signal)
user_authenticated = Signal()  # providing_args=['user', 'request', 'auth_method']


def get_client_ip(request):
    """Extract client IP from request (handles proxies/load balancers)."""
    if not request:
        return None
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def get_user_agent(request):
    """Extract user agent from request."""
    if not request:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")


@receiver(user_logged_in)
def update_last_login_on_session_login(sender, user, request, **kwargs):
    """
    Update last_login when user logs in via Django session authentication.

    This handles:
    - Django admin login
    - Session-based authentication
    """
    from .models import AuditLog

    now = timezone.now()
    user.last_login = now
    user.save(update_fields=["last_login"])

    # Create audit log entry for login
    AuditLog.objects.create(
        user=user,
        action="LOGIN",
        resource_type="user",
        resource_id=str(user.user_id),
        changes={"auth_method": "session", "login_time": now.isoformat()},
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )

    logger.info(f"Session login: {user.username} ({user.email}) from {get_client_ip(request)}")


@receiver(user_authenticated)
def update_last_login_on_token_auth(sender, user, request=None, auth_method="token", **kwargs):
    """
    Update last_login when user authenticates via token (Firebase, WebSocket).

    This handles:
    - Firebase ID token authentication
    - WebSocket JWT authentication
    - API token authentication

    Note: We throttle updates to prevent database writes on every API request.
    Updates only occur if last login was more than 5 minutes ago.
    """
    from .models import AuditLog

    # Throttle updates: only update if last login was more than 5 minutes ago
    # This prevents database writes on every API request
    now = timezone.now()
    should_update = user.last_login is None or (now - user.last_login).total_seconds() > 300

    if should_update:
        user.last_login = now
        user.save(update_fields=["last_login"])

        # Create audit log entry for login (throttled like last_login)
        AuditLog.objects.create(
            user=user,
            action="LOGIN",
            resource_type="user",
            resource_id=str(user.user_id),
            changes={"auth_method": auth_method, "login_time": now.isoformat()},
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )

        logger.info(f"{auth_method.capitalize()} auth: {user.username} ({user.email}) - last_login updated")
    else:
        logger.debug(f"{auth_method.capitalize()} auth: {user.username} - last_login throttled (recent)")
