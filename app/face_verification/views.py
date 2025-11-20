"""
Face Verification API Views

Endpoints for triggering and checking backend verification
"""

import logging

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from bus_kiosk_backend.core.authentication import CloudTasksAuthentication
from events.models import BoardingEvent

from .tasks import verify_boarding_event

logger = logging.getLogger(__name__)


@api_view(["POST"])
@authentication_classes([CloudTasksAuthentication])
@permission_classes([AllowAny])
def verify_event_handler(request):
    """
    Cloud Tasks handler for async boarding event verification

    This endpoint is called by Cloud Tasks to verify boarding events
    using multi-model consensus.

    Authentication: CloudTasksAuthentication (validates Cloud Tasks headers)

    Request Body:
        {
            "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV"  # ULID
        }

    Response:
        {
            "status": "success",
            "event_id": "...",
            "verification_status": "verified",
            "confidence_level": "high",
            "student_id": 123,
            "kiosk_student_id": 123,
            "is_mismatch": false
        }
    """
    event_id = request.data.get("event_id")

    if not event_id:
        logger.error("Missing event_id in request")
        return Response({"error": "event_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    logger.info(f"Received verification request for event {event_id}")

    # Run verification task
    result = verify_boarding_event(event_id)

    if result["status"] == "success":
        return Response(result, status=status.HTTP_200_OK)
    elif result["status"] == "error":
        return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        return Response(result, status=status.HTTP_200_OK)


@api_view(["GET"])
def get_verification_status(request, event_id):
    """
    Get verification status for a boarding event

    GET /api/v1/face-verification/events/{event_id}/

    Response:
        {
            "event_id": "...",
            "backend_verification_status": "verified",
            "backend_verification_confidence": "high",
            "backend_student_id": 123,
            "kiosk_student_id": 123,
            "has_mismatch": false,
            "needs_manual_review": false,
            "backend_verified_at": "2025-01-15T10:30:00Z",
            "model_consensus_data": {
                "mobilefacenet": {...},
                "arcface": {...},
                "adaface": {...}
            }
        }
    """
    try:
        event = BoardingEvent.objects.get(event_id=event_id)

        return Response(
            {
                "event_id": event.event_id,
                "backend_verification_status": event.backend_verification_status,
                "backend_verification_confidence": event.backend_verification_confidence,
                "backend_student_id": event.backend_student_id,
                "kiosk_student_id": event.student_id,
                "has_mismatch": event.has_verification_mismatch,
                "needs_manual_review": event.needs_manual_review,
                "backend_verified_at": event.backend_verified_at,
                "model_consensus_data": event.model_consensus_data,
            },
            status=status.HTTP_200_OK,
        )
    except BoardingEvent.DoesNotExist:
        return Response({"error": "Event not found"}, status=status.HTTP_404_NOT_FOUND)
