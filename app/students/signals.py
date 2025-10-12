"""
Signals for automatic face recognition processing.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import StudentPhoto
from .services.face_recognition_service import FaceRecognitionService

logger = logging.getLogger(__name__)


@receiver(post_save, sender=StudentPhoto)
def process_student_photo_embedding(sender, instance: StudentPhoto, created, **kwargs):
    """
    Automatically process student photos for face embeddings when uploaded.

    This signal handler is triggered whenever a StudentPhoto is saved.
    If it's a new photo (created=True), it will attempt to generate
    face embeddings.
    """
    # Only process new photos
    if not created:
        return

    # Skip if photo file is not provided
    if not instance.photo:
        logger.debug(f"No photo file for student photo {instance.photo_id}")
        return

    try:
        logger.info(f"Starting automatic embedding generation for photo {instance.photo_id}")

        # Initialize the face recognition service
        service = FaceRecognitionService()

        # Process the photo
        success = service.process_student_photo(instance)

        if success:
            logger.info(f"Successfully generated embeddings for photo {instance.photo_id}")
        else:
            logger.warning(f"Failed to generate embeddings for photo {instance.photo_id}")

    except Exception as e:
        logger.error(f"Error in automatic embedding generation for photo {instance.photo_id}: {e}")
        # Don't re-raise the exception to avoid breaking the photo save operation
