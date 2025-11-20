"""
Face Verification Tasks

Handles async verification of boarding events using Cloud Tasks
"""

import logging
from datetime import datetime
from typing import Dict, List

import numpy as np
from django.utils import timezone

from events.models import BoardingEvent
from students.models import FaceEmbeddingMetadata

from .services import FaceVerificationConsensusService

logger = logging.getLogger(__name__)


def verify_boarding_event(event_id: str) -> Dict:
    """
    Verify a boarding event using multi-model consensus

    This function is called asynchronously by Cloud Tasks after a boarding
    event is created by the kiosk.

    Args:
        event_id: BoardingEvent primary key (ULID)

    Returns:
        Dict with verification results
    """
    try:
        # Load boarding event
        event = BoardingEvent.objects.get(event_id=event_id)
        logger.info(f"Processing verification for event {event_id}, kiosk predicted: {event.student_id}")

        # Check if we have confirmation faces to verify
        if not event.confirmation_face_1_gcs:
            logger.warning(f"No confirmation faces for event {event_id}, skipping verification")
            event.backend_verification_status = "failed"
            event.backend_verified_at = timezone.now()
            event.save(update_fields=["backend_verification_status", "backend_verified_at"])
            return {"status": "failed", "reason": "no_confirmation_faces"}

        # Load face image from GCS
        from events.services.storage_service import BoardingEventStorageService

        storage_service = BoardingEventStorageService()

        # Use first confirmation face (highest quality typically)
        face_image_bytes = storage_service.download_file(event.confirmation_face_1_gcs)

        # Convert to numpy array
        import cv2

        face_image = cv2.imdecode(np.frombuffer(face_image_bytes, np.uint8), cv2.IMREAD_COLOR)
        face_image = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)

        # Load all student embeddings from database
        student_embeddings = _load_student_embeddings()

        if not student_embeddings:
            logger.warning("No student embeddings found in database")
            event.backend_verification_status = "failed"
            event.backend_verified_at = timezone.now()
            event.save(update_fields=["backend_verification_status", "backend_verified_at"])
            return {"status": "failed", "reason": "no_embeddings"}

        # Run consensus verification
        consensus_service = FaceVerificationConsensusService()
        result = consensus_service.verify_face(face_image, student_embeddings)

        # Update boarding event with results
        event.backend_verification_status = result.verification_status
        event.backend_verification_confidence = result.confidence_level
        event.backend_student_id = result.student_id
        event.model_consensus_data = result.model_results
        event.backend_verified_at = timezone.now()

        event.save(
            update_fields=[
                "backend_verification_status",
                "backend_verification_confidence",
                "backend_student_id",
                "model_consensus_data",
                "backend_verified_at",
            ]
        )

        logger.info(
            f"Verification complete for event {event_id}: "
            f"status={result.verification_status}, "
            f"confidence={result.confidence_level}, "
            f"student={result.student_id}, "
            f"kiosk_match={event.student_id == result.student_id}"
        )

        # Log if there's a mismatch
        if event.student_id != result.student_id:
            logger.warning(
                f"MISMATCH: Kiosk predicted {event.student_id}, "
                f"backend predicted {result.student_id} "
                f"(confidence: {result.confidence_level})"
            )

        return {
            "status": "success",
            "event_id": event_id,
            "verification_status": result.verification_status,
            "confidence_level": result.confidence_level,
            "student_id": result.student_id,
            "kiosk_student_id": event.student_id,
            "is_mismatch": event.student_id != result.student_id,
        }

    except BoardingEvent.DoesNotExist:
        logger.error(f"Boarding event {event_id} not found")
        return {"status": "error", "reason": "event_not_found"}
    except Exception as e:
        logger.error(f"Failed to verify event {event_id}: {e}", exc_info=True)
        # Update event as failed
        try:
            event = BoardingEvent.objects.get(event_id=event_id)
            event.backend_verification_status = "failed"
            event.backend_verified_at = timezone.now()
            event.save(update_fields=["backend_verification_status", "backend_verified_at"])
        except Exception:
            pass
        return {"status": "error", "reason": str(e)}


def _load_student_embeddings() -> Dict[int, List[Dict]]:
    """
    Load all student embeddings from database

    Returns:
        Dict mapping student_id to list of embeddings per model
        Format: {
            student_id: [
                {'model': 'mobilefacenet', 'embedding': np.array(...)},
                {'model': 'arcface', 'embedding': np.array(...)}
            ]
        }
    """
    embeddings_qs = FaceEmbeddingMetadata.objects.select_related("student_photo__student").filter(
        embedding__isnull=False
    )

    student_embeddings: Dict[int, List[Dict]] = {}

    for emb_meta in embeddings_qs:
        student_id = emb_meta.student_photo.student_id

        if student_id not in student_embeddings:
            student_embeddings[student_id] = []

        # Convert pgvector to numpy array
        embedding_array = np.array(emb_meta.embedding, dtype=np.float32)

        student_embeddings[student_id].append({"model": emb_meta.model_name, "embedding": embedding_array})

    logger.info(f"Loaded embeddings for {len(student_embeddings)} students")

    return student_embeddings
