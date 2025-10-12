"""
MobileFaceNet TFLite Inference
Optimized for production - matches frontend exactly.
LAZY LOADING: TensorFlow is imported only when model is actually loaded.
"""

from typing import TYPE_CHECKING, cast

import numpy as np

from ml_models.config import MOBILEFACENET_CONFIG

from .base import BaseFaceRecognitionModel

if TYPE_CHECKING:
    pass


class MobileFaceNet(BaseFaceRecognitionModel):
    """
    MobileFaceNet implementation using TensorFlow Lite.
    Same model as frontend - zero drift guaranteed.
    """

    def __init__(self):
        model_path = MOBILEFACENET_CONFIG["model_path"]
        super().__init__(model_path)

    def _validate_model(self) -> None:
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        if self.model_path.suffix != ".tflite":
            raise ValueError("Model must be .tflite format")

    def _load_model(self) -> None:
        """Load TFLite model - lazy import tensorflow here."""
        import tensorflow as tf

        self.interpreter = tf.lite.Interpreter(model_path=str(self.model_path))
        self.interpreter.allocate_tensors()

        # Get input/output details
        self.input_details = self.interpreter.get_input_details()[0]
        self.output_details = self.interpreter.get_output_details()[0]

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image to match frontend preprocessing.

        Args:
            image: RGB image (HxWx3), values 0-255

        Returns:
            Preprocessed image, shape (1, 112, 112, 3), values -1 to 1
        """
        # Resize to 112x112
        import cv2

        image = cv2.resize(image, (112, 112))

        # Normalize: (pixel - 127.5) / 128.0
        mean = np.array(MOBILEFACENET_CONFIG["mean"], dtype=np.float32)
        std = np.array(MOBILEFACENET_CONFIG["std"], dtype=np.float32)
        image = (image.astype(np.float32) - mean) / std

        # Add batch dimension and ensure float32
        image = np.expand_dims(image, axis=0).astype(np.float32)

        return image

    def predict(self, preprocessed_image: np.ndarray) -> np.ndarray:
        """Run TFLite inference."""
        self.interpreter.set_tensor(self.input_details["index"], preprocessed_image)
        self.interpreter.invoke()
        output = self.interpreter.get_tensor(self.output_details["index"])
        return output

    def postprocess(self, raw_output: np.ndarray) -> np.ndarray:
        """
        L2 normalize embedding (same as frontend).

        Args:
            raw_output: Raw model output (1, 192)

        Returns:
            Normalized embedding (192,)
        """
        embedding = raw_output.squeeze()  # Remove batch dim

        # L2 normalization
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding

    @property
    def input_shape(self) -> tuple[int, int, int]:
        return cast(tuple[int, int, int], MOBILEFACENET_CONFIG["input_shape"])

    @property
    def embedding_dims(self) -> int:
        return cast(int, MOBILEFACENET_CONFIG["output_dims"])
