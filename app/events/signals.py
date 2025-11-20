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
    2. Only triggers for NEW events (created=True)
    3. Creates a Cloud Task for async face verification
    4. Fails gracefully if Cloud Tasks is unavailable (local dev)
    """
    if not created:
        # Only verify new events, not updates
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
