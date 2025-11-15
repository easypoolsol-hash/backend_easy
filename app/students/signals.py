"""
Signals for automatic face recognition processing and parent auto-creation.

Google-style architecture:
- User creation is automatic (authentication layer)
- Parent creation is automatic (domain layer)
- Admin approval is manual (authorization layer)
"""

import logging
from typing import TYPE_CHECKING, Any

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Parent, StudentPhoto

if TYPE_CHECKING:
    from users.models import User as UserType
else:
    UserType = None

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=StudentPhoto)
def process_student_photo_embedding(
    sender: type[StudentPhoto],
    instance: StudentPhoto,
    created: bool,
    **kwargs: Any,
) -> None:
    """
    Automatically process student photos for face embeddings when uploaded.

    This signal handler triggers asynchronous processing to avoid:
    - Blocking the upload response
    - HTTP context issues in web container
    - Memory constraints during ML processing

    If Celery/Redis is unavailable (e.g., in CI or development), the task
    queuing will fail gracefully without breaking photo uploads.
    """
    # Only process new photos
    if not created:
        return

    # Skip if photo data is not provided
    if not instance.photo_data:
        logger.debug(f"No photo data for student photo {instance.photo_id}")
        return

    # Process embedding synchronously (simple approach for Cloud Run)
    try:
        from .services.face_recognition_service import FaceRecognitionService

        logger.info(f"Processing embedding for photo {instance.photo_id}")
        service = FaceRecognitionService()
        success = service.process_student_photo(instance)

        if success:
            logger.info(f"✅ Successfully generated embeddings for photo {instance.photo_id}")
        else:
            logger.warning(f"⚠️ Failed to generate embeddings for photo {instance.photo_id}")
    except Exception as e:
        # Log error but don't crash - photo upload should still succeed
        photo_id = instance.photo_id
        logger.error(f"❌ Error processing embedding for {photo_id}: {e}")
        logger.info("Photo uploaded, embedding generation failed")


@receiver(post_save, sender=User)
def auto_create_parent_for_new_user(
    sender: type["UserType"],  # type: ignore[misc]
    instance: "UserType",  # type: ignore[misc]
    created: bool,
    **kwargs: Any,
) -> None:
    """
    Auto-create Parent record when a new User signs in.

    Flow (Google-style self-service):
    1. User signs in with Google (Firebase)
    2. User record auto-created in database
    3. User gets "New User" group (no permissions)
    4. This signal auto-creates linked Parent record
    5. Parent gets approval_status='pending'
    6. Admin fills PII, links children, approves
    7. Parent gets access to app

    Note: PII fields left empty for security - admin fills during approval.
    """
    if not created:
        return

    # Only create Parent for users in "New User" or "Parent" group
    is_parent_user = instance.groups.filter(name__in=["New User", "Parent"]).exists()
    if not is_parent_user:
        logger.debug(f"Skipping Parent creation for non-parent user {instance.username}")
        return

    # Check if parent profile already exists
    if hasattr(instance, "parent_profile") and instance.parent_profile:
        logger.info(f"Parent profile already exists for user {instance.username}")
        return

    # Auto-create Parent record with empty PII (admin fills later)
    try:
        # Use dummy encrypted values for PII fields (admin will update)
        # We need to set them to avoid unique constraint issues
        import uuid

        temp_suffix = uuid.uuid4().hex[:8]
        parent = Parent(
            user=instance,
            approval_status="pending",
        )
        # Set temporary encrypted values for PII
        parent.encrypted_email = f"pending-{temp_suffix}@example.com"
        parent.encrypted_phone = f"+91{temp_suffix[:10].zfill(10)}"
        parent.encrypted_name = f"Pending User {instance.username}"
        parent.save()

        logger.info(f"✅ Auto-created Parent record for user {instance.username} (approval pending)")
    except Exception as e:  # nosec B110
        logger.error(f"❌ Failed to auto-create Parent for user {instance.username}: {e}")
