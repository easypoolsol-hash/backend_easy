"""
Signal handlers for boarding events
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import BoardingEvent

logger = logging.getLogger(__name__)


@receiver(post_save, sender=BoardingEvent)
def trigger_face_verification(sender, instance, created, **kwargs):
    """
    Automatically trigger face verification via Cloud Tasks when a boarding event is created.

    This signal handler:
    1. Runs after every BoardingEvent is saved
    2. Only triggers when confirmation faces are ACTUALLY uploaded (not on initial create)
    3. Creates a Cloud Task for async face verification
    4. Fails gracefully if Cloud Tasks is unavailable (local dev)

    IMPORTANT: We check for confirmation_face_1_gcs because:
    - Initial create() happens BEFORE GCS upload (confirmation_face_1_gcs is empty)
    - Second save() happens AFTER GCS upload (confirmation_face_1_gcs is set)
    - This prevents the race condition where verification runs before images are uploaded
    """
    # Only trigger when confirmation faces are actually uploaded
    # This prevents race condition: signal fires on create() BEFORE GCS upload
    if not instance.confirmation_face_1_gcs:
        if created:
            logger.debug(f"[FACE-VERIFICATION] Skipping verification for {instance.event_id} - no confirmation faces yet")
        return

    # Check if this is the update that adds the GCS paths (not initial create)
    # We use update_fields to detect this - serializer uses update_fields=[confirmation_face_*_gcs]
    update_fields = kwargs.get("update_fields")
    if update_fields and "confirmation_face_1_gcs" not in update_fields:
        # This is an update but not for confirmation faces
        return

    # Skip if already verified (prevent re-verification on other updates)
    if instance.backend_verification_status in ["verified", "flagged", "failed"]:
        logger.debug(f"[FACE-VERIFICATION] Skipping {instance.event_id} - already verified")
        return

    try:
        from face_verification.cloud_tasks_client import create_verification_task

        logger.info(f"[FACE-VERIFICATION] Triggering verification for boarding event {instance.event_id}")

        task_name = create_verification_task(str(instance.event_id))

        if task_name:
            logger.info(f"[FACE-VERIFICATION] Task created: {task_name}")
        else:
            logger.warning(f"[FACE-VERIFICATION] Task creation failed for event {instance.event_id}")

    except Exception as e:
        logger.error(f"[FACE-VERIFICATION] Error triggering verification for event {instance.event_id}: {e}", exc_info=True)
        # Don't fail the boarding event creation if verification fails
        # Verification can be retried manually if needed
