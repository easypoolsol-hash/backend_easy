"""
Face Recognition Service
Handles automatic embedding generation for student photos.
Industry Standard: Clean architecture - ML logic separated in ml_models/
"""

from __future__ import annotations

from importlib import import_module
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.core.files.base import File
else:
    from django.core.files.base import File as FileType

    File = FileType  # type: ignore[misc, assignment]

from ..face_recognition_config import (
    FACE_RECOGNITION_CONFIG,
    get_enabled_models,
)
from ..models import FaceEmbeddingMetadata, StudentPhoto

logger = logging.getLogger(__name__)


class FaceRecognitionService:
    """
    Service for processing student photos and generating face embeddings.
    LAZY LOADING: ML libraries only loaded when photo is processed.
    """

    def __init__(self) -> None:
        self.enabled_models = get_enabled_models()
        self.config = FACE_RECOGNITION_CONFIG
        self._model_instances: dict[str, Any] = {}
        self._face_detector: Any = None  # Lazy load on first use

    def process_student_photo(self, student_photo: StudentPhoto) -> bool:
        """
        Process a student photo and generate embeddings for all enabled models.

        Args:
            student_photo: StudentPhoto instance to process

        Returns:
            bool: True if processing was successful
        """
        try:
            logger.info(f"Processing photo for student {student_photo.student}")

            # Load and validate image
            image = self._load_image(student_photo.photo)
            if not image:
                logger.error("Failed to load image")
                return False

            # Detect and validate faces
            faces = self._detect_faces(image)
            if not faces:
                logger.warning("No faces detected in photo")
                return False

            max_faces_val = self.config.get("max_faces_per_image", 1)
            max_faces = int(max_faces_val) if isinstance(max_faces_val, (int, float)) else 1
            if len(faces) > max_faces:
                logger.warning(f"Too many faces detected: {len(faces)} > {max_faces}")
                return False

            # Process the best face
            best_face = self._select_best_face(faces)
            embedding_data = self._generate_embeddings(best_face)

            if not embedding_data:
                logger.error("Failed to generate embeddings")
                return False

            # Save embeddings to database
            self._save_embeddings(student_photo, embedding_data)

            logger.info(f"Successfully processed photo for student {student_photo.student}")
            return True

        except Exception as e:
            logger.error(f"Error processing student photo: {e}")
            return False

    def _load_image(self, photo_file: File[Any]) -> Any:
        """Load and validate image from file."""
        from PIL import Image

        try:
            pil_image = Image.open(photo_file)
            pil_image.verify()  # Validate image integrity
            photo_file.seek(0)  # Reset file pointer
            pil_image = Image.open(photo_file)  # Re-open after verify

            # Convert to RGB if necessary
            if pil_image.mode != "RGB":
                pil_image = pil_image.convert("RGB")

            return pil_image
        except Exception as e:
            logger.error(f"Error loading image: {e}")
            return None

    def _detect_faces(self, image: Any) -> list[dict[str, Any]]:
        """
        Detect faces using OpenCV (lightweight).
        Returns list of face dictionaries with bbox and confidence.
        """
        import numpy as np
        from PIL import Image

        # Lazy load face detector on first use
        if self._face_detector is None:
            from ml_models.face_recognition.preprocessing.face_detector import (
                FaceDetector,
            )

            self._face_detector = FaceDetector()

        # Convert PIL to numpy
        img_array = np.array(image)

        # Real face detection
        detections = self._face_detector.detect(img_array)

        if not detections:
            return []

        # Convert to dict format with cropped face
        faces = []
        for detection in detections:
            face_crop = self._face_detector.crop_face(img_array, detection)
            faces.append(
                {
                    "bbox": detection.bbox,
                    "confidence": detection.confidence,
                    "image": Image.fromarray(face_crop),
                }
            )

        return faces

    def _select_best_face(self, faces: list[dict[str, Any]]) -> dict[str, Any]:
        """Select highest confidence face."""
        return max(faces, key=lambda f: f["confidence"])

    def _generate_embeddings(self, face_data: dict[str, Any]) -> dict[str, Any]:
        """
        Generate embeddings for all enabled models.
        """
        import numpy as np

        embeddings = {}
        face_image = face_data["image"]

        for model_name, model_config in self.enabled_models.items():
            try:
                logger.debug(f"Generating embedding with model: {model_name}")

                # Get or create model instance
                model = self._get_model_instance(model_name, model_config)

                # Convert face to numpy array (RGB, 0-255)
                face_array = np.array(face_image)

                # Generate embedding (model handles preprocessing internally)
                embedding = model.generate_embedding(face_array)

                # Validate embedding quality
                quality_score = self._calculate_embedding_quality(embedding)
                if quality_score < model_config["quality_threshold"]:
                    logger.warning(f"Embedding quality too low for {model_name}: {quality_score} < {model_config['quality_threshold']}")
                    continue

                embeddings[model_name] = {
                    "vector": embedding.tolist(),
                    "quality_score": quality_score,
                    "dimensions": len(embedding),
                }

            except Exception as e:
                logger.error(f"Error generating embedding for {model_name}: {e}")
                continue

        return embeddings

    def _get_model_instance(self, model_name: str, model_config: dict[str, Any]) -> Any:
        """
        Dynamically load model instance (Factory Pattern).
        Industry standard: lazy loading.
        """
        if model_name not in self._model_instances:
            # Parse class path
            module_path, class_name = model_config["class"].rsplit(".", 1)

            # Import module and get class
            module = import_module(module_path)
            model_class = getattr(module, class_name)

            # Instantiate model
            self._model_instances[model_name] = model_class()
            logger.info(f"Loaded model: {model_name}")

        return self._model_instances[model_name]

    def _calculate_embedding_quality(self, embedding: Any) -> float:
        """Calculate quality score for embedding."""
        import numpy as np

        # Simple quality metric based on vector magnitude and variance
        magnitude = np.linalg.norm(embedding)
        variance = np.var(embedding)

        quality = min(float(magnitude / 10.0), 1.0) * min(float(variance * 100.0), 1.0)
        return float(quality)

    def _save_embeddings(self, student_photo: StudentPhoto, embedding_data: dict[str, Any]) -> None:
        """Save embeddings to database."""
        for model_name, data in embedding_data.items():
            FaceEmbeddingMetadata.objects.create(
                student_photo=student_photo,
                model_name=model_name,
                embedding=data["vector"],
                quality_score=data["quality_score"],
                captured_at=student_photo.captured_at,
            )
