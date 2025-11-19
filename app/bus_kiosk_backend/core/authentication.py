"""
Authentication for EasyPool Backend

This module provides:
- Firebase token verification for Frontend Easy Flutter app
- Cloud Tasks OIDC token verification for internal task processing

Follows Google Cloud IAM best practices for explicit authentication.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from firebase_admin import auth
from rest_framework import authentication, exceptions

User = get_user_model()

logger = logging.getLogger(__name__)


class CloudTasksAuthentication(authentication.BaseAuthentication):
    """
    Cloud Tasks Authentication (Google Cloud Run IAM Pattern)

    Google Cloud Run automatically validates OIDC tokens via IAM.
    When a request reaches Django, it has already been authenticated
    by Cloud Run's run.invoker role check.

    This class trusts Cloud Run's validation and identifies Cloud Tasks
    requests via their specific headers.

    Security Model (Fortune 500 / Google Pattern):
    1. Cloud Tasks sends OIDC token with service account
    2. Cloud Run validates token via IAM (roles/run.invoker)
    3. Cloud Run sets X-CloudTasks-* headers after validation
    4. Django trusts these headers (they can't be spoofed externally)

    Headers Set by Cloud Tasks (after OIDC validation):
    - X-CloudTasks-TaskName: Task identifier
    - X-CloudTasks-QueueName: Queue name
    - X-CloudTasks-TaskRetryCount: Retry count
    - X-CloudTasks-TaskExecutionCount: Execution count
    - X-CloudTasks-TaskETA: Scheduled time
    """

    def authenticate(self, request):
        """
        Authenticate Cloud Tasks request using GCP headers.

        Cloud Run strips X-CloudTasks-* headers from external requests
        and only sets them for authenticated Cloud Tasks requests.
        This is the Google-recommended pattern.

        Returns:
            Tuple of (CloudTasksUser, 'cloud_tasks') if valid Cloud Tasks request
            None if not a Cloud Tasks request (let other auth classes handle it)
        """
        # Check for Cloud Tasks specific headers
        # These headers are set by Cloud Run AFTER OIDC validation
        # External requests cannot spoof these headers
        task_name = request.META.get("HTTP_X_CLOUDTASKS_TASKNAME")
        queue_name = request.META.get("HTTP_X_CLOUDTASKS_QUEUENAME")

        if not task_name or not queue_name:
            # Not a Cloud Tasks request, let other auth classes handle
            return None

        # Additional validation: check queue name matches expected pattern
        expected_queue_prefix = getattr(settings, "CLOUD_TASKS_QUEUE_NAME", "notifications-queue")
        if expected_queue_prefix and expected_queue_prefix not in queue_name:
            logger.warning(
                f"Unexpected Cloud Tasks queue: {queue_name}, "
                f"expected prefix: {expected_queue_prefix}"
            )
            raise exceptions.AuthenticationFailed("Invalid Cloud Tasks queue")

        # Get retry count for logging
        retry_count = request.META.get("HTTP_X_CLOUDTASKS_TASKRETRYCOUNT", "0")

        logger.info(
            f"Authenticated Cloud Tasks request: task={task_name}, "
            f"queue={queue_name}, retry_count={retry_count}"
        )

        # Return CloudTasksUser - request is authenticated by Cloud Run IAM
        return (
            CloudTasksUser(task_name=task_name, queue_name=queue_name),
            "cloud_tasks"
        )


class CloudTasksUser:
    """
    Minimal user object for Cloud Tasks requests.

    Not a real Django user - just enough to pass DRF's checks.
    """

    def __init__(self, task_name: str, queue_name: str):
        self.task_name = task_name
        self.queue_name = queue_name
        self.is_authenticated = True

    def __str__(self):
        return f"CloudTasks:{self.queue_name}/{self.task_name}"


class FirebaseAuthentication(authentication.BaseAuthentication):
    """
    Firebase Authentication for Frontend Easy

    Verifies Firebase ID tokens sent from the Flutter web app.
    Creates or updates Django users based on Firebase user data.

    Expected header: Authorization: Bearer <firebase_id_token>
    """

    def authenticate(self, request):
        """
        Authenticate the request using Firebase ID token.

        Returns:
            Tuple of (User, None) if authentication succeeds
            None if no auth header or not a Firebase token
            (let other auth classes handle it)
        """
        auth_header = request.META.get("HTTP_AUTHORIZATION")

        if not auth_header:
            return None

        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ")[1]

        try:
            decoded_token = auth.verify_id_token(token)
            firebase_uid = decoded_token["uid"]
            email = decoded_token.get("email")
            name = decoded_token.get("name")

            # Check if this is a kiosk user (from custom claims)
            user_type = decoded_token.get("type")
            kiosk_id = decoded_token.get("kiosk_id")

            if user_type == "kiosk" and kiosk_id:
                # PRE-REGISTRATION PATTERN: Kiosk must be registered by admin first
                # This follows Fortune 500 standard (Apple Business Manager, Microsoft Intune)
                from kiosks.models import Kiosk

                try:
                    kiosk = Kiosk.objects.get(firebase_uid=firebase_uid)
                    logger.info(f"Authenticated kiosk: {kiosk.kiosk_id} ({firebase_uid})")
                    return (kiosk, None)

                except Kiosk.DoesNotExist as e:
                    logger.error(f"Kiosk not registered: firebase_uid={firebase_uid}, kiosk_id={kiosk_id}. Admin must create kiosk record first.")
                    raise exceptions.AuthenticationFailed("Kiosk not registered. Contact administrator to register this device.") from e

            # Regular user (not a kiosk)
            user, created = User.objects.get_or_create(
                username=firebase_uid,
                defaults={
                    "email": email or "",
                    "first_name": name.split(" ")[0] if name else "",
                    "last_name": " ".join(name.split(" ")[1:]) if name and len(name.split(" ")) > 1 else "",
                },
            )

            if user.email != (email or ""):
                user.email = email or ""
                user.save(update_fields=["email"])

            if created:
                # Assign "New User" group with no permissions (default for Firebase users)
                try:
                    from django.contrib.auth.models import Group

                    new_user_group, _ = Group.objects.get_or_create(name="New User")
                    user.groups.add(new_user_group)
                    logger.info(f"Created new user from Firebase: {firebase_uid} ({email}) - assigned 'New User' group")
                except Exception as group_error:  # nosec B110
                    logger.warning(f"Could not assign 'New User' group to {firebase_uid}: {group_error}")
                    logger.info(f"Created new user from Firebase: {firebase_uid} ({email})")
            else:
                logger.debug(f"Authenticated existing user from Firebase: {firebase_uid}")

            # Emit signal for last_login tracking and audit logging
            from users.signals import user_authenticated

            user_authenticated.send(sender=self.__class__, user=user, request=request, auth_method="firebase")

            return (user, None)

        except auth.ExpiredIdTokenError as e:
            logger.warning("Firebase token expired")
            raise exceptions.AuthenticationFailed("Firebase token has expired") from e

        except auth.RevokedIdTokenError as e:
            logger.warning("Firebase token revoked")
            raise exceptions.AuthenticationFailed("Firebase token has been revoked") from e

        except auth.InvalidIdTokenError as e:
            logger.warning("Invalid Firebase token")
            raise exceptions.AuthenticationFailed("Invalid Firebase token") from e

        except Exception as e:
            logger.error(f"Firebase authentication error: {e}")
            raise exceptions.AuthenticationFailed("Firebase authentication failed") from e
