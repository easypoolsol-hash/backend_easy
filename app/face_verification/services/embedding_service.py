"""
Embedding Service - Single Responsibility: Student Embeddings

Handles:
- Loading student face embeddings from database
- Organizing embeddings by student and model type
- Caching for performance
"""

import logging

import numpy as np

from students.models import FaceEmbeddingMetadata

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for loading and managing student face embeddings"""

    @staticmethod
    def load_all_student_embeddings() -> dict[int, list[dict]]:
        """
        Load all student embeddings from database

        Returns:
            Dict mapping student_id to list of embeddings per model
            Format: {
                student_id: [
                    {'model': 'mobilefacenet', 'embedding': np.array(...), 'quality': 0.95},
                    {'model': 'arcface_int8', 'embedding': np.array(...), 'quality': 0.92}
                ]
            }
        """
        embeddings_qs = FaceEmbeddingMetadata.objects.select_related("student_photo__student").filter(embedding__isnull=False)

        student_embeddings: dict[int, list[dict]] = {}
        loaded_count = 0

        for emb_meta in embeddings_qs:
            try:
                student_id = emb_meta.student_photo.student.student_id

                # Convert stored embedding to numpy array
                embedding_array = EmbeddingService._convert_to_numpy(emb_meta.embedding)

                if embedding_array is None:
                    continue

                # Initialize student entry if needed
                if student_id not in student_embeddings:
                    student_embeddings[student_id] = []

                student_embeddings[student_id].append(
                    {
                        "model": emb_meta.model_name,
                        "embedding": embedding_array,
                        "quality": emb_meta.quality_score or 0.0,
                        "photo_id": str(emb_meta.student_photo.photo_id),
                    }
                )
                loaded_count += 1

            except Exception as e:
                logger.warning(f"Failed to load embedding {emb_meta.embedding_id}: {e}")
                continue

        logger.info(f"Loaded {loaded_count} embeddings for {len(student_embeddings)} students")
        return student_embeddings

    @staticmethod
    def _convert_to_numpy(embedding_data) -> np.ndarray | None:
        """
        Convert stored embedding data to numpy array

        Handles various storage formats:
        - Already numpy array
        - List of floats
        - JSON string
        - Bytes
        """
        if embedding_data is None:
            return None

        # Already numpy array
        if isinstance(embedding_data, np.ndarray):
            return embedding_data

        # List of floats
        if isinstance(embedding_data, list):
            return np.array(embedding_data, dtype=np.float32)

        # JSON string
        if isinstance(embedding_data, str):
            import json

            try:
                data = json.loads(embedding_data)
                return np.array(data, dtype=np.float32)
            except (json.JSONDecodeError, ValueError):
                return None

        # Bytes (numpy save format)
        if isinstance(embedding_data, bytes):
            try:
                import io

                return np.load(io.BytesIO(embedding_data))
            except Exception:
                return None

        return None

    @staticmethod
    def get_embeddings_for_student(student_id: int) -> list[dict]:
        """
        Get all embeddings for a specific student

        Args:
            student_id: Student primary key

        Returns:
            List of embedding dicts for this student
        """
        embeddings_qs = FaceEmbeddingMetadata.objects.select_related("student_photo").filter(
            student_photo__student_id=student_id, embedding__isnull=False
        )

        embeddings = []
        for emb_meta in embeddings_qs:
            embedding_array = EmbeddingService._convert_to_numpy(emb_meta.embedding)
            if embedding_array is not None:
                embeddings.append(
                    {
                        "model": emb_meta.model_name,
                        "embedding": embedding_array,
                        "quality": emb_meta.quality_score or 0.0,
                    }
                )

        return embeddings
