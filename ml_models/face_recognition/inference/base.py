"""
Base class for face recognition models.
Follows Abstract Factory pattern - industry standard.
"""

from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np


class BaseFaceRecognitionModel(ABC):
    """
    Abstract base class for all face recognition models.
    Ensures consistent interface across different models.
    """

    def __init__(self, model_path: Path):
        self.model_path = model_path
        self._validate_model()
        self._load_model()

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
