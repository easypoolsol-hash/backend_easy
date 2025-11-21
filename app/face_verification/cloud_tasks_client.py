"""
Cloud Tasks Client for Face Verification

Handles creating Cloud Tasks for async verification
"""

import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def create_verification_task(event_id: str) -> str | None:
    """
    Create a Cloud Task for async face verification

    Args:
        event_id: BoardingEvent primary key (ULID)

    Returns:
        Task name if successful, None if failed
    """
    try:
        # Import Cloud Tasks client
        from google.cloud import tasks_v2

        client = tasks_v2.CloudTasksClient()

        # Configure task
        project = settings.GCP_PROJECT_ID
        location = settings.GCP_REGION
        queue = settings.FACE_VERIFICATION_QUEUE_NAME

        parent = client.queue_path(project, location, queue)

        # Build task payload
        payload = {"event_id": event_id}

        # Build task request
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": f"{settings.BACKEND_URL}/api/v1/face-verification/verify/",
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": json.dumps(payload).encode(),
                "oidc_token": {
                    "service_account_email": settings.CLOUD_TASKS_SERVICE_ACCOUNT,
                },
            }
        }

        # Create the task
        response = client.create_task(request={"parent": parent, "task": task})

        logger.info(f"✅ Created verification task for event {event_id}: {response.name}")
        return response.name

    except ImportError:
        logger.warning("google-cloud-tasks not installed, skipping task creation (local development?)")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to create verification task for event {event_id}: {e}", exc_info=True)
        return None


def create_verification_task_local(event_id: str) -> dict:
    """
    Local/development version that runs verification synchronously

    Used when Cloud Tasks is not available (local development)
    """
    logger.info(f"Running verification locally for event {event_id}")

    from .tasks import verify_boarding_event

    result = verify_boarding_event(event_id)

    logger.info(f"Local verification complete for event {event_id}: {result}")
    return result
