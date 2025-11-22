"""
InsightFace W600K ResNet50 ONNX Inference
Part of buffalo_l model pack - production-ready face recognition model
Trained on WebFace600K dataset - 99.65%+ LFW accuracy
Uses ONNXRuntime for fast, production-ready inference
"""

from pathlib import Path

import numpy as np

from .base import BaseFaceRecognitionModel


class W600kResNet50(BaseFaceRecognitionModel):
    """
    InsightFace W600K ResNet50 - buffalo_l recognition model.
    Production-proven, widely used in banking/security systems.
    174MB model size, 512-dimensional embeddings.
    Supports loading from local path or GCS URL.
    """

    def __init__(self, model_source: str | Path | None = None):
        """
        Initialize W600K ResNet50 model.

        Args:
            model_source: Local path, GCS URL (gs://...), or None for default path
        """
        if model_source is None:
            model_source = Path(__file__).parent.parent / "models" / "w600k_r50.onnx"
        super().__init__(model_source)
        self.session = None  # Lazy loaded ONNX session

    def _validate_model(self) -> None:
        if self.is_gcs:
            # For GCS, just check we have bytes
            if not self.model_bytes:
                raise ValueError("Model bytes not loaded from GCS")
        else:
            # For local files, check path exists
            if not self.model_path or not self.model_path.exists():
                raise FileNotFoundError(f"W600K ResNet50 model not found: {self.model_path}")
            if self.model_path.suffix != ".onnx":
                raise ValueError("W600K model must be .onnx format")

    def _load_model(self) -> None:
        """Load ONNX model from bytes or path using ONNXRuntime"""
        import onnxruntime as ort

        if self.is_gcs:
            # Load from bytes
            self.session = ort.InferenceSession(self.model_bytes, providers=["CPUExecutionProvider"])
        else:
            # Load from file path
            self.session = ort.InferenceSession(str(self.model_path), providers=["CPUExecutionProvider"])

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for W600K ResNet50.

        Args:
            image: RGB image (HxWx3), values 0-255

        Returns:
            Preprocessed image, shape (1, 3, 112, 112), NCHW format
        """
        import cv2

        # Resize to 112x112
        image = cv2.resize(image, (112, 112))

        # Keep RGB format (InsightFace models expect RGB)
        # Normalize: subtract mean 127.5, divide by std 127.5
        mean = np.array([127.5, 127.5, 127.5], dtype=np.float32)
        image = image.astype(np.float32) - mean
        image = image / 127.5  # Range: [-1, 1]

        # Transpose from HWC to CHW format (ONNX uses NCHW)
        image = np.transpose(image, (2, 0, 1))

        # Add batch dimension
        image = np.expand_dims(image, axis=0)

        return image

    def predict(self, preprocessed_image: np.ndarray) -> np.ndarray:
        """Run ONNX inference"""
        # Lazy load model on first use
        if self.session is None:
            self._load_model()

        # Get input name from model
        input_name = self.session.get_inputs()[0].name

        # Run inference
        outputs = self.session.run(None, {input_name: preprocessed_image})

        return outputs[0]

    def postprocess(self, raw_output: np.ndarray) -> np.ndarray:
        """
        L2 normalize embedding.

        Args:
            raw_output: Raw model output (1, 512)

        Returns:
            Normalized embedding (512,)
        """
        embedding = raw_output.squeeze()  # Remove batch dim (512,)

        # L2 normalization
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding

    @property
    def input_shape(self) -> tuple[int, int, int]:
        return (112, 112, 3)

    @property
    def embedding_dims(self) -> int:
        return 512
