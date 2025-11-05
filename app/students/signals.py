"""
Signals for automatic face recognition processing.
"""

import logging
from typing import Any

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import StudentPhoto

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

    # Skip if photo file is not provided
    if not instance.photo:
        logger.debug(f"No photo file for student photo {instance.photo_id}")
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
