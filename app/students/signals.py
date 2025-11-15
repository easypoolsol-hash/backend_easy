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

from .models import StudentPhoto

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


# REMOVED: Auto-create parent signal
# Parents are now created explicitly via /api/v1/parents/register/ endpoint
# Called from parent_easy app after Firebase login.
# This ensures only users from parent app get Parent records.
