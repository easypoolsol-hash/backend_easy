"""
Base class for face recognition models.
Follows Abstract Factory pattern - industry standard.
Supports loading from local paths or GCS URLs.
"""

from abc import ABC, abstractmethod
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


class BaseFaceRecognitionModel(ABC):
    """
    Abstract base class for all face recognition models.
    Ensures consistent interface across different models.
    Supports loading from local filesystem or Google Cloud Storage.
    """

    def __init__(self, model_source: str | Path):
        """
        Initialize model from local path or GCS URL.

        Args:
            model_source: Either a local Path or GCS URL (gs://bucket/path)
        """
        self.model_source = model_source
        self.is_gcs = isinstance(model_source, str) and model_source.startswith("gs://")
        self.model_bytes: bytes | None = None
        self.model_path: Path | None = None

        if self.is_gcs:
            logger.info(f"Loading model from GCS: {model_source}")
            self.model_bytes = self._download_from_gcs(model_source)
        else:
            self.model_path = Path(model_source) if isinstance(model_source, str) else model_source

        self._validate_model()
        self._load_model()

    def _download_from_gcs(self, gcs_url: str) -> bytes:
        """
        Download model from GCS to memory.

        Args:
            gcs_url: GCS URL in format gs://bucket/path

        Returns:
            Model file contents as bytes
        """
        from google.cloud import storage

        # Parse gs://bucket/path
        parts = gcs_url.replace("gs://", "").split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid GCS URL format: {gcs_url}")

        bucket_name, blob_path = parts[0], parts[1]

        logger.info(f"Downloading from GCS: bucket={bucket_name}, path={blob_path}")

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)

        model_bytes = blob.download_as_bytes()
        logger.info(f"Downloaded {len(model_bytes) / (1024 * 1024):.1f} MB from GCS")

        return model_bytes

    @abstractmethod
    def _validate_model(self) -> None:
        """Validate model file exists and is correct format."""
        pass

    @abstractmethod
    def _load_model(self) -> None:
        """Load model into memory."""
        pass

    @abstractmethod
    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for model input.

        Args:
            image: RGB image as numpy array (HxWx3)

        Returns:
            Preprocessed image ready for inference
        """
        pass

    @abstractmethod
    def predict(self, preprocessed_image: np.ndarray) -> np.ndarray:
        """
        Run inference on preprocessed image.

        Args:
            preprocessed_image: Output from preprocess()

        Returns:
            Embedding vector
        """
        pass

    @abstractmethod
    def postprocess(self, raw_output: np.ndarray) -> np.ndarray:
        """
        Postprocess model output (normalize, etc).

        Args:
            raw_output: Raw model output

        Returns:
            Final embedding vector (normalized)
        """
        pass

    def generate_embedding(self, image: np.ndarray) -> np.ndarray:
        """
        Main entry point: image → embedding.
        Template Method pattern.

        Args:
            image: RGB image (HxWx3)

        Returns:
            Normalized embedding vector
        """
        preprocessed = self.preprocess(image)
        raw_output = self.predict(preprocessed)
        embedding = self.postprocess(raw_output)
        return embedding

    @property
    @abstractmethod
    def input_shape(self) -> tuple[int, int, int]:
        """Expected input shape (H, W, C)."""
        pass

    @property
    @abstractmethod
    def embedding_dims(self) -> int:
        """Output embedding dimensions."""
        pass
