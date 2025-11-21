"""
Multi-Model Consensus Service

Implements banking-grade verification using 3-model voting:
- ArcFace (99.82% LFW accuracy) - placeholder: MobileFaceNet
- AdaFace (Quality adaptive) - placeholder: MobileFaceNet
- MobileFaceNet (Fast verification)

Architecture:
1. Load all 3 models
2. Run inference on each model independently
3. Apply voting/consensus strategy
4. Return aggregated result with confidence level
"""

from dataclasses import dataclass
import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ModelResult:
    """Result from a single model"""

    model_name: str
    student_id: str | None  # UUID as string for JSON serialization
    confidence_score: float
    all_scores: dict[str, float]  # {student_id: score} for debugging


@dataclass
class ConsensusResult:
    """Final consensus result from all models"""

    student_id: str | None  # UUID as string for JSON serialization
    confidence_level: str  # 'high', 'medium', 'low'
    consensus_count: int  # How many models agreed
    model_results: dict[str, dict[str, Any]]  # Detailed results from each model
    verification_status: str  # 'verified', 'flagged', 'failed'


class FaceVerificationConsensusService:
    """
    Multi-model consensus service for face verification

    Uses voting strategy:
    - All 3 models agree → HIGH confidence, VERIFIED
    - 2 models agree → MEDIUM confidence, VERIFIED
    - No consensus → LOW confidence, FLAGGED for review
    - No matches → FAILED
    """

    def __init__(self) -> None:
        """Initialize service with all enabled models"""
        from ml_models.config import FACE_RECOGNITION_MODELS, MULTI_MODEL_CONFIG

        self.config: dict[str, Any] = MULTI_MODEL_CONFIG
        models_for_verification: list[str] = self.config.get("models_for_verification", [])  # type: ignore[assignment]
        self.enabled_models: dict[str, dict[str, Any]] = {
            name: config for name, config in FACE_RECOGNITION_MODELS.items() if config.get("enabled", False) and name in models_for_verification
        }

        self.models: dict[str, Any] = {}  # Lazy loaded
        logger.info(f"Initialized ConsensusService with {len(self.enabled_models)} models: {list(self.enabled_models.keys())}")

    def _load_models(self) -> None:
        """Lazy load all models on first use"""
        if self.models:
            return

        logger.info("Loading face recognition models...")

        for model_name, config in self.enabled_models.items():
            try:
                # Import model class dynamically
                class_path: str = config["class"]  # type: ignore[assignment]
                module_path, class_name = class_path.rsplit(".", 1)
                module = __import__(module_path, fromlist=[class_name])
                model_class = getattr(module, class_name)

                # Instantiate model (models determine their own paths)
                self.models[model_name] = model_class()

                logger.info(f"✅ Loaded model: {model_name}")
            except Exception as e:
                logger.error(f"❌ Failed to load model {model_name}: {e}", exc_info=True)
                raise

        logger.info(f"All {len(self.models)} models loaded successfully")

    def verify_face(self, face_image: np.ndarray, student_embeddings: dict[str, list[dict[str, Any]]]) -> ConsensusResult:
        """
        Run multi-model verification with consensus voting

        Args:
            face_image: Face image (RGB, any size - will be preprocessed by models)
            student_embeddings: Dict mapping student_id to list of embeddings per model
                Format: {
                    student_id: [
                        {'model': 'mobilefacenet', 'embedding': np.array(...)},
                        {'model': 'arcface', 'embedding': np.array(...)}
                    ]
                }

        Returns:
            ConsensusResult with final decision and detailed breakdown
        """
        self._load_models()

        logger.info(f"Running verification with {len(self.models)} models on {len(student_embeddings)} students")

        # Step 1: Run all models
        model_results: list[ModelResult] = []
        for model_name, model in self.models.items():
            try:
                result = self._run_single_model(model_name=model_name, model=model, face_image=face_image, student_embeddings=student_embeddings)
                model_results.append(result)
                logger.info(f"Model {model_name}: predicted={result.student_id}, score={result.confidence_score:.3f}")
            except Exception as e:
                logger.error(f"Model {model_name} failed: {e}", exc_info=True)
                # Continue with other models

        # Step 2: Apply consensus voting
        consensus = self._apply_consensus_voting(model_results)

        logger.info(
            f"Consensus: student={consensus.student_id}, "
            f"confidence={consensus.confidence_level}, "
            f"status={consensus.verification_status}, "
            f"agreement={consensus.consensus_count}/{len(model_results)}"
        )

        return consensus

    def _run_single_model(
        self, model_name: str, model: Any, face_image: np.ndarray, student_embeddings: dict[str, list[dict[str, Any]]]
    ) -> ModelResult:
        """Run inference on a single model"""

        # Get threshold for this model
        threshold: float = self.enabled_models[model_name]["quality_threshold"]  # type: ignore[assignment]

        # Generate embedding for input face
        try:
            face_embedding = model.generate_embedding(face_image)
        except Exception as e:
            logger.error(f"Failed to generate embedding with {model_name}: {e}")
            return ModelResult(model_name=model_name, student_id=None, confidence_score=0.0, all_scores={})

        # Compare with all student embeddings for this model
        best_student_id: str | None = None
        best_score = 0.0
        all_scores: dict[str, float] = {}

        for student_id, embedding_list in student_embeddings.items():
            # Get embeddings for this specific model
            model_embeddings = [emb_dict["embedding"] for emb_dict in embedding_list if emb_dict["model"] == model_name]

            if not model_embeddings:
                continue

            # Calculate similarity with each stored embedding (max score)
            scores = [self._cosine_similarity(face_embedding, stored_emb) for stored_emb in model_embeddings]
            max_score = max(scores) if scores else 0.0
            all_scores[student_id] = max_score

            # Check if this is the best match and meets threshold
            if max_score > best_score and max_score >= threshold:
                best_score = max_score
                best_student_id = student_id

        return ModelResult(
            model_name=model_name,
            student_id=best_student_id,
            confidence_score=best_score,
            all_scores=all_scores,
        )

    def _apply_consensus_voting(self, model_results: list[ModelResult]) -> ConsensusResult:
        """
        Apply voting consensus strategy

        Rules:
        - All models agree → HIGH confidence, VERIFIED
        - 2+ models agree → MEDIUM confidence, VERIFIED
        - No consensus → LOW confidence, FLAGGED
        - No matches → FAILED
        """

        # Count votes for each student
        votes: dict[str | None, list[ModelResult]] = {}
        for result in model_results:
            student_id = result.student_id
            if student_id not in votes:
                votes[student_id] = []
            votes[student_id].append(result)

        # Remove None votes (failed matches)
        votes.pop(None, None)

        if not votes:
            # No model found any match
            return ConsensusResult(
                student_id=None,
                confidence_level="low",
                consensus_count=0,
                model_results={r.model_name: self._format_model_result(r) for r in model_results},
                verification_status="failed",
            )

        # Get winning student (most votes)
        winning_student = max(votes.items(), key=lambda x: len(x[1]))
        student_id, agreeing_models = winning_student
        consensus_count = len(agreeing_models)
        total_models = len(model_results)

        # Determine confidence level and status
        minimum_consensus: int = self.config.get("minimum_consensus", 2)  # type: ignore[assignment]
        if consensus_count == total_models:
            confidence_level = "high"
            verification_status = "verified"
        elif consensus_count >= minimum_consensus:
            confidence_level = "medium"
            verification_status = "verified"
        else:
            confidence_level = "low"
            verification_status = "flagged"

        return ConsensusResult(
            student_id=student_id,
            confidence_level=confidence_level,
            consensus_count=consensus_count,
            model_results={r.model_name: self._format_model_result(r) for r in model_results},
            verification_status=verification_status,
        )

    @staticmethod
    def _format_model_result(result: ModelResult) -> dict[str, Any]:
        """Format ModelResult for JSON storage"""
        return {
            "student_id": result.student_id,
            "confidence_score": float(result.confidence_score),
            "top_5_scores": dict(sorted(result.all_scores.items(), key=lambda x: x[1], reverse=True)[:5]) if result.all_scores else {},
        }

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings"""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
