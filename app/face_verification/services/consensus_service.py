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
    confidence_score: float  # Best score from agreeing models
    confidence_level: str  # 'high', 'medium', 'low'
    consensus_count: int  # How many models agreed
    model_results: dict[str, dict[str, Any]]  # Detailed results from each model
    verification_status: str  # 'verified', 'flagged', 'failed'
    config_version: int | None  # Version of ML config used (for tracking)


class FaceVerificationConsensusService:
    """
    Multi-model consensus service for face verification

    Uses voting strategy:
    - All 3 models agree → HIGH confidence, VERIFIED
    - 2 models agree → MEDIUM confidence, VERIFIED
    - No consensus → LOW confidence, FLAGGED for review
    - No matches → FAILED
    """

    def __init__(self, use_database_config: bool = True) -> None:
        """
        Initialize service with all enabled models from database

        Args:
            use_database_config: If True, load config from database (FaceRecognitionModel).
                                If False, use static config from ml_models/config.py
        """
        # Load configuration from database or fallback to static config
        self.config_version: int | None = None
        self.enabled_models: dict[str, dict[str, Any]] = {}

        if use_database_config:
            try:
                # Import here to avoid circular dependency
                from ml_config.models import BackendModelConfiguration, FaceRecognitionModel

                # Get active consensus configuration
                active_config = BackendModelConfiguration.get_active_config()
                self.config_version = active_config.version

                # Get enabled models from database
                db_models = FaceRecognitionModel.get_enabled_models()

                if not db_models.exists():
                    logger.warning("No enabled models in database, creating defaults...")
                    FaceRecognitionModel.create_default_models()
                    db_models = FaceRecognitionModel.get_enabled_models()

                # Build enabled_models dict from database
                for model in db_models:
                    self.enabled_models[model.name] = {
                        "enabled": True,
                        "class": model.inference_class,
                        "quality_threshold": model.threshold,
                        "weight": model.weight,
                        "temperature_scaling": {
                            "enabled": model.temperature_enabled,
                            "temperature": model.temperature,
                            "shift": model.shift,
                        },
                        "gcs_bucket": model.gcs_bucket,
                        "gcs_path": model.gcs_path,
                        "local_filename": model.local_filename,
                    }

                self.config: dict[str, Any] = {
                    "enabled": True,
                    "models_for_verification": list(self.enabled_models.keys()),
                    "consensus_strategy": "weighted",
                    "minimum_consensus": active_config.minimum_consensus,
                }

                # Store full ensemble config for use in weighted voting
                self.ensemble_config = active_config.to_dict()

                logger.info(
                    f"Loaded ML config V{self.config_version} from database "
                    f"with {len(self.enabled_models)} models: {list(self.enabled_models.keys())}"
                )

            except Exception as e:
                logger.warning(f"Failed to load database config: {e}. Falling back to static config.")
                self._load_static_config()
        else:
            self._load_static_config()

        self.models: dict[str, Any] = {}  # Lazy loaded
        logger.info(f"Initialized ConsensusService with {len(self.enabled_models)} models: {list(self.enabled_models.keys())}")
        if self.config_version:
            logger.info(f"Using ML Configuration Version: {self.config_version}")

    def _load_static_config(self) -> None:
        """Fallback: Load static config from ml_models/config.py"""
        from ml_models.config import FACE_RECOGNITION_MODELS, MULTI_MODEL_CONFIG

        self.config = MULTI_MODEL_CONFIG
        self.ensemble_config = {}

        models_for_verification: list[str] = self.config.get("models_for_verification", [])  # type: ignore[assignment]
        self.enabled_models = {
            name: config for name, config in FACE_RECOGNITION_MODELS.items() if config.get("enabled", False) and name in models_for_verification
        }

    def _load_models(self) -> None:
        """Lazy load all models on first use from GCS or local paths"""
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

                # Build GCS URL if we have GCS config, otherwise use default local path
                if "gcs_bucket" in config and "gcs_path" in config:
                    gcs_url = f"gs://{config['gcs_bucket']}/{config['gcs_path']}"
                    logger.info(f"Loading {model_name} from GCS: {gcs_url}")
                    self.models[model_name] = model_class(model_source=gcs_url)
                else:
                    # Use default local path
                    logger.info(f"Loading {model_name} from local filesystem")
                    self.models[model_name] = model_class()

                logger.info(f"✅ Loaded model: {model_name}")
            except Exception as e:
                logger.error(f"❌ Failed to load model {model_name}: {e}", exc_info=True)
                raise

        logger.info(f"All {len(self.models)} models loaded successfully")

    def verify_face(
        self, face_image: np.ndarray, student_embeddings: dict[str, list[dict[str, Any]]], enable_cascading: bool = True
    ) -> ConsensusResult:
        """
        Run multi-model verification with cascading strategy for optimal performance

        Banking-grade cascading:
        - Stage 1 (Fast Path): Try MobileFaceNet alone first
          - If confidence >= 0.75 → Accept (resolves ~80% of cases in <100ms)
        - Stage 2 (Accurate Path): Full ensemble for uncertain cases
          - MobileFaceNet + ArcFace + AdaFace (when enabled)

        Args:
            face_image: Face image (RGB, any size - will be preprocessed by models)
            student_embeddings: Dict mapping student_id to list of embeddings per model
                Format: {
                    student_id: [
                        {'model': 'mobilefacenet', 'embedding': np.array(...)},
                        {'model': 'arcface', 'embedding': np.array(...)}
                    ]
                }
            enable_cascading: If True, use cascading strategy. If False, run all models.

        Returns:
            ConsensusResult with final decision and detailed breakdown
        """
        self._load_models()

        logger.info(f"Running verification with {len(self.models)} models on {len(student_embeddings)} students")

        # Banking-grade cascading strategy
        if enable_cascading and "mobilefacenet" in self.models:
            # Stage 1: Fast path with MobileFaceNet only
            logger.info("Stage 1: Running MobileFaceNet (fast path)")
            fast_result = self._run_single_model(
                model_name="mobilefacenet", model=self.models["mobilefacenet"], face_image=face_image, student_embeddings=student_embeddings
            )

            # Check if we can accept this result (high confidence, clear winner)
            if fast_result.confidence_score >= 0.75 and fast_result.student_id is not None:
                # Format result to check for ambiguity
                formatted_result = self._format_model_result(fast_result)

                # Only accept if not ambiguous (clear gap between #1 and #2)
                if not formatted_result.get("is_ambiguous", False):
                    logger.info(
                        f"✅ Fast path: student={fast_result.student_id}, "
                        f"score={fast_result.confidence_score:.3f}, gap={formatted_result['top_k_gap']:.3f}"
                    )

                    # Return single-model result with high confidence
                    return ConsensusResult(
                        student_id=fast_result.student_id,
                        confidence_score=fast_result.confidence_score,
                        confidence_level="high",
                        consensus_count=1,
                        model_results={"mobilefacenet": formatted_result},
                        verification_status="verified",
                        config_version=self.config_version,
                    )
                else:
                    logger.info(f"⚠️ Fast path rejected (ambiguous): gap={formatted_result['top_k_gap']:.3f} < 0.12. Escalating to full ensemble.")
            else:
                logger.info(f"⚠️ Fast path rejected (low confidence): score={fast_result.confidence_score:.3f} < 0.75. Escalating to full ensemble.")

        # Stage 2: Full ensemble (either cascading failed or disabled)
        logger.info("Stage 2: Running full ensemble (accurate path)")
        model_results: list[ModelResult] = []
        for model_name, model in self.models.items():
            try:
                result = self._run_single_model(model_name=model_name, model=model, face_image=face_image, student_embeddings=student_embeddings)
                model_results.append(result)
                logger.info(f"Model {model_name}: predicted={result.student_id}, score={result.confidence_score:.3f}")
            except Exception as e:
                logger.error(f"Model {model_name} failed: {e}", exc_info=True)
                # Continue with other models

        # Apply consensus voting
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
                confidence_score=0.0,
                confidence_level="low",
                consensus_count=0,
                model_results={r.model_name: self._format_model_result(r) for r in model_results},
                verification_status="failed",
                config_version=self.config_version,
            )

        # Get winning student (most votes)
        winning_student = max(votes.items(), key=lambda x: len(x[1]))
        student_id, agreeing_models = winning_student
        consensus_count = len(agreeing_models)
        total_models = len(model_results)

        # Get best confidence score from agreeing models
        best_score = max(m.confidence_score for m in agreeing_models)

        # Format all model results (includes top-K gap calculation)
        formatted_results = {r.model_name: self._format_model_result(r) for r in model_results}

        # Banking-grade enhancement: Check for ambiguous cases (small top-K gap)
        has_ambiguous_match = any(result.get("is_ambiguous", False) for result in formatted_results.values())

        # Determine confidence level and status
        minimum_consensus: int = self.config.get("minimum_consensus", 2)  # type: ignore[assignment]
        if consensus_count == total_models and not has_ambiguous_match:
            confidence_level = "high"
            verification_status = "verified"
        elif consensus_count >= minimum_consensus and not has_ambiguous_match:
            confidence_level = "medium"
            verification_status = "verified"
        elif consensus_count >= minimum_consensus and has_ambiguous_match:
            # Has consensus but gap is small (e.g., Lalit vs ADVIK) - flag for review
            confidence_level = "medium"
            verification_status = "flagged"
        else:
            confidence_level = "low"
            verification_status = "flagged"

        return ConsensusResult(
            student_id=student_id,
            confidence_score=best_score,
            confidence_level=confidence_level,
            consensus_count=consensus_count,
            model_results=formatted_results,
            verification_status=verification_status,
            config_version=self.config_version,
        )

    @staticmethod
    def _format_model_result(result: ModelResult) -> dict[str, Any]:
        """
        Format ModelResult for JSON storage with top-K gap analysis

        Banking-grade enhancement: Track gap between top-2 matches to detect ambiguous cases
        """
        # Get top-5 matches sorted by score
        top_5_sorted = sorted(result.all_scores.items(), key=lambda x: x[1], reverse=True)[:5] if result.all_scores else []
        top_5_dict = dict(top_5_sorted)

        # Calculate top-K gap (difference between #1 and #2)
        top_k_gap = 0.0
        is_ambiguous = False

        if len(top_5_sorted) >= 2:
            top_1_score = top_5_sorted[0][1]
            top_2_score = top_5_sorted[1][1]
            top_k_gap = float(top_1_score - top_2_score)

            # Banking standard: gap < 0.12 indicates ambiguous case (e.g., Lalit vs ADVIK)
            is_ambiguous = top_k_gap < 0.12

        return {
            "student_id": result.student_id,
            "confidence_score": float(result.confidence_score),
            "top_5_scores": top_5_dict,
            "top_k_gap": top_k_gap,  # Gap between #1 and #2
            "is_ambiguous": is_ambiguous,  # True if gap < 0.12
        }

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings"""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
