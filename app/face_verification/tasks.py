"""
Face Verification Tasks - Single Responsibility: Orchestration

This module ONLY orchestrates the verification process.
Actual work is delegated to specialized services:
- ImageService: Load and convert images
- EmbeddingService: Load student embeddings
- MultiCropService: Multi-crop voting strategy

Called asynchronously by Cloud Tasks after a boarding event is created.
"""

import logging

from django.utils import timezone

from events.models import BoardingEvent

from .services.embedding_service import EmbeddingService
from .services.image_service import ImageService
from .services.multi_crop_service import MultiCropService

logger = logging.getLogger(__name__)


def verify_boarding_event(event_id: str) -> dict:
    """
    Verify a boarding event using multi-model consensus with multi-crop voting

    ORCHESTRATOR ONLY - delegates actual work to specialized services:
    1. ImageService: Load ALL confirmation face crops (not just first one!)
    2. EmbeddingService: Load student embeddings from database
    3. MultiCropService: Run multi-crop verification with voting strategy

    Args:
        event_id: BoardingEvent primary key (ULID)

    Returns:
        Dict with verification results
    """
    try:
        # Step 1: Load boarding event
        event = BoardingEvent.objects.get(event_id=event_id)
        logger.info(f"[VERIFY] Starting verification for event {event_id}, kiosk predicted: {event.student_id}")

        # Step 2: Load ALL confirmation face crops (not just first one!)
        try:
            crop_images = ImageService.load_all_confirmation_faces(event)
            logger.info(f"[VERIFY] Loaded {len(crop_images)} crop images for event {event_id}")
        except ValueError as e:
            logger.warning(f"[VERIFY] No confirmation faces for event {event_id}: {e}")
            _mark_event_failed(event, "no_confirmation_faces")
            return {"status": "failed", "reason": "no_confirmation_faces"}

        # Step 3: Load student embeddings
        student_embeddings = EmbeddingService.load_all_student_embeddings()

        if not student_embeddings:
            logger.warning("[VERIFY] No student embeddings found in database")
            _mark_event_failed(event, "no_embeddings")
            return {"status": "failed", "reason": "no_embeddings"}

        logger.info(f"[VERIFY] Loaded embeddings for {len(student_embeddings)} students")

        # Step 4: Run multi-crop verification with voting strategy
        multi_crop_service = MultiCropService()
        result = multi_crop_service.verify_with_multiple_crops(crop_images, student_embeddings)

        # Step 5: Save results to event
        _save_verification_result(event, result)

        # Step 6: Log result
        _log_verification_result(event, result)

        return {
            "status": "success",
            "event_id": event_id,
            "verification_status": result.verification_status,
            "confidence_level": result.confidence_level,
            "student_id": result.student_id,
            "kiosk_student_id": str(event.student_id) if event.student_id else None,
            "is_mismatch": str(event.student_id) != str(result.student_id) if result.student_id else True,
            "voting_details": result.voting_details,
        }

    except BoardingEvent.DoesNotExist:
        logger.error(f"[VERIFY] Boarding event {event_id} not found")
        return {"status": "error", "reason": "event_not_found"}

    except Exception as e:
        logger.error(f"[VERIFY] Failed to verify event {event_id}: {e}", exc_info=True)
        _mark_event_failed_safe(event_id, str(e))
        return {"status": "error", "reason": str(e)}


def _mark_event_failed(event: BoardingEvent, reason: str) -> None:
    """Mark a boarding event as failed verification"""
    event.backend_verification_status = "failed"
    event.backend_verified_at = timezone.now()
    event.model_consensus_data = {"failure_reason": reason}
    event.backend_config_version = None  # No config used for failed verification
    event.save(
        update_fields=[
            "backend_verification_status",
            "backend_verified_at",
            "model_consensus_data",
            "backend_config_version",
        ]
    )


def _mark_event_failed_safe(event_id: str, reason: str) -> None:
    """Safely mark event as failed (handles missing event)"""
    try:
        event = BoardingEvent.objects.get(event_id=event_id)
        _mark_event_failed(event, reason)
    except Exception:
        pass


def _save_verification_result(event: BoardingEvent, result) -> None:
    """Save multi-crop verification result to boarding event"""
    # Build model consensus data including voting details
    model_consensus_data = {
        "model_results": result.model_results,
        "voting_details": result.voting_details,
        "confidence_score": result.confidence_score,
    }

    event.backend_verification_status = result.verification_status
    event.backend_verification_confidence = result.confidence_level
    event.backend_student_id = result.student_id
    event.model_consensus_data = model_consensus_data
    event.backend_verified_at = timezone.now()
    event.backend_config_version = result.config_version  # Track which config was used

    event.save(
        update_fields=[
            "backend_verification_status",
            "backend_verification_confidence",
            "backend_student_id",
            "model_consensus_data",
            "backend_verified_at",
            "backend_config_version",
        ]
    )


def _log_verification_result(event: BoardingEvent, result) -> None:
    """Log verification result with mismatch detection"""
    kiosk_student = str(event.student_id) if event.student_id else "Unknown"
    backend_student = str(result.student_id) if result.student_id else "Unknown"

    logger.info(
        f"[VERIFY] Complete for event {event.event_id}: "
        f"status={result.verification_status}, "
        f"confidence={result.confidence_level}, "
        f"student={backend_student}, "
        f"kiosk_match={kiosk_student == backend_student}"
    )

    # Log mismatch warning
    if kiosk_student != backend_student:
        logger.warning(
            f"[VERIFY] MISMATCH: Kiosk predicted {kiosk_student}, backend predicted {backend_student} (confidence: {result.confidence_level})"
        )

    # Log voting details
    voting = result.voting_details
    logger.info(
        f"[VERIFY] Voting: {voting.get('reason', 'unknown')}, "
        f"crops_used={voting.get('total_crops', 0)}, "
        f"distribution={voting.get('vote_distribution', {})}"
    )
