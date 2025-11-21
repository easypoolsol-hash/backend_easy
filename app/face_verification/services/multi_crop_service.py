"""
Multi-Crop Service - Single Responsibility: Multi-Crop Voting Strategy

Handles:
- Running verification on multiple crop images
- Applying voting strategy (majority voting / best score)
- Aggregating results from multiple crops
"""

from dataclasses import dataclass
import logging

import numpy as np

from .consensus_service import FaceVerificationConsensusService

logger = logging.getLogger(__name__)


@dataclass
class CropResult:
    """Result from verifying a single crop image"""

    crop_index: int
    student_id: str | None  # UUID as string for JSON serialization
    confidence_score: float
    confidence_level: str  # high, medium, low
    verification_status: str  # verified, flagged, failed
    model_results: dict


@dataclass
class MultiCropResult:
    """Aggregated result from multi-crop voting"""

    student_id: str | None  # UUID as string for JSON serialization
    confidence_score: float
    confidence_level: str
    verification_status: str
    model_results: dict
    voting_details: dict  # Details about how voting was decided
    config_version: int | None  # ML config version used


class MultiCropService:
    """Service for multi-crop verification with voting strategy"""

    def __init__(self):
        self.consensus_service = FaceVerificationConsensusService()

    def verify_with_multiple_crops(self, crop_images: list[np.ndarray], student_embeddings: dict[str, list[dict]]) -> MultiCropResult:
        """
        Run verification on ALL crop images and apply voting strategy

        Strategy:
        1. Verify each crop independently using consensus service
        2. Apply majority voting across crops
        3. If 2+ crops agree on student → HIGH confidence
        4. If all disagree → Use highest confidence result

        Args:
            crop_images: List of face crop images (RGB numpy arrays)
            student_embeddings: Dict of student_id → embeddings

        Returns:
            MultiCropResult with aggregated verification result
        """
        if not crop_images:
            return MultiCropResult(
                student_id=None,
                confidence_score=0.0,
                confidence_level="low",
                verification_status="failed",
                model_results={},
                voting_details={"reason": "no_crop_images"},
                config_version=self.consensus_service.config_version,
            )

        # Step 1: Verify each crop independently
        crop_results = self._verify_all_crops(crop_images, student_embeddings)

        if not crop_results:
            return MultiCropResult(
                student_id=None,
                confidence_score=0.0,
                confidence_level="low",
                verification_status="failed",
                model_results={},
                voting_details={"reason": "all_crops_failed"},
                config_version=self.consensus_service.config_version,
            )

        # Step 2: Apply voting strategy
        final_result = self._apply_voting_strategy(crop_results)

        logger.info(
            f"Multi-crop verification complete: "
            f"student={final_result.student_id}, "
            f"confidence={final_result.confidence_level}, "
            f"crops_used={len(crop_results)}"
        )

        return final_result

    def _verify_all_crops(self, crop_images: list[np.ndarray], student_embeddings: dict[str, list[dict]]) -> list[CropResult]:
        """
        Verify each crop image independently

        Args:
            crop_images: List of crop images
            student_embeddings: Student embeddings dict

        Returns:
            List of CropResult for each successful crop verification
        """
        crop_results = []

        for i, crop_image in enumerate(crop_images):
            try:
                logger.debug(f"Verifying crop {i + 1}/{len(crop_images)}")

                # Run consensus verification on this crop
                result = self.consensus_service.verify_face(crop_image, student_embeddings)

                crop_result = CropResult(
                    crop_index=i + 1,
                    student_id=result.student_id,
                    confidence_score=result.confidence_score if hasattr(result, "confidence_score") else 0.0,
                    confidence_level=result.confidence_level,
                    verification_status=result.verification_status,
                    model_results=result.model_results if hasattr(result, "model_results") else {},
                )

                crop_results.append(crop_result)
                logger.info(f"Crop {i + 1} result: student={crop_result.student_id}, confidence={crop_result.confidence_level}")

            except Exception as e:
                logger.error(f"Failed to verify crop {i + 1}: {e}")
                # Continue with other crops
                continue

        return crop_results

    def _apply_voting_strategy(self, crop_results: list[CropResult]) -> MultiCropResult:
        """
        Apply majority voting strategy across crop results

        Voting logic:
        1. Count how many crops voted for each student
        2. If 2+ crops agree → Use that student with boosted confidence
        3. If single crop or all disagree → Use highest confidence result
        4. Track voting details for transparency

        Args:
            crop_results: List of CropResult from each crop

        Returns:
            MultiCropResult with final decision
        """
        # Count votes for each student
        votes: dict[str | None, list[CropResult]] = {}
        for crop_result in crop_results:
            student_id = crop_result.student_id
            if student_id not in votes:
                votes[student_id] = []
            votes[student_id].append(crop_result)

        # Find the winner (most votes)
        sorted_votes = sorted(votes.items(), key=lambda x: len(x[1]), reverse=True)

        # Build voting details for transparency
        voting_details = {
            "total_crops": len(crop_results),
            "vote_distribution": {str(k): len(v) for k, v in votes.items()},
            "crop_results": [
                {
                    "crop": r.crop_index,
                    "student_id": r.student_id,
                    "confidence": r.confidence_level,
                    "score": r.confidence_score,
                }
                for r in crop_results
            ],
        }

        if not sorted_votes:
            return MultiCropResult(
                student_id=None,
                confidence_score=0.0,
                confidence_level="low",
                verification_status="failed",
                model_results={},
                voting_details={**voting_details, "reason": "no_votes"},
                config_version=self.consensus_service.config_version,
            )

        winning_student, winning_crops = sorted_votes[0]
        vote_count = len(winning_crops)

        # Decision logic based on vote count
        if vote_count >= 2:
            # Majority (2+ crops agree) → HIGH confidence
            best_crop = max(winning_crops, key=lambda x: x.confidence_score)
            voting_details["reason"] = f"majority_vote_{vote_count}_crops"
            voting_details["confidence_boost"] = "majority_agreement"

            # Boost confidence if not already high
            confidence_level = "high" if best_crop.confidence_level != "low" else "medium"

            return MultiCropResult(
                student_id=winning_student,
                confidence_score=best_crop.confidence_score,
                confidence_level=confidence_level,
                verification_status="verified" if winning_student else "failed",
                model_results=best_crop.model_results,
                voting_details=voting_details,
                config_version=self.consensus_service.config_version,
            )
        else:
            # No majority → Use highest confidence crop
            best_crop = max(crop_results, key=lambda x: x.confidence_score)
            voting_details["reason"] = "highest_confidence_single_crop"

            return MultiCropResult(
                student_id=best_crop.student_id,
                confidence_score=best_crop.confidence_score,
                confidence_level=best_crop.confidence_level,
                verification_status=best_crop.verification_status,
                model_results=best_crop.model_results,
                voting_details=voting_details,
                config_version=self.consensus_service.config_version,
            )
