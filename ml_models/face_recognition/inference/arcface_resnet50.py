"""
ArcFace ResNet50 ONNX Inference (W600K dataset)
99.77% accuracy on LFW benchmark - Banking-grade face recognition
Uses ONNXRuntime for fast, production-ready inference
"""

from pathlib import Path

import numpy as np

from .base import BaseFaceRecognitionModel


class ArcFaceResNet50(BaseFaceRecognitionModel):
    """
    ArcFace with ResNet50 backbone trained on W600K dataset.
    99.77% accuracy on LFW benchmark.
    Outputs 512-dimensional face embeddings.
    """

    def __init__(self):
        model_path = Path(__file__).parent.parent / "models" / "arcface_w600k_r50.onnx"
        super().__init__(model_path)
        self.session = None  # Lazy loaded ONNX session

    def _validate_model(self) -> None:
        if not self.model_path.exists():
            raise FileNotFoundError(f"ArcFace ResNet50 model not found: {self.model_path}")
        if self.model_path.suffix != ".onnx":
            raise ValueError("ArcFace model must be .onnx format")

    def _load_model(self) -> None:
        """Load ONNX model using ONNXRuntime"""
        import onnxruntime as ort

        # Create inference session with CPU provider
        self.session = ort.InferenceSession(str(self.model_path), providers=["CPUExecutionProvider"])

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for ArcFace ResNet50.

        Args:
            image: RGB image (HxWx3), values 0-255

        Returns:
            Preprocessed image, shape (1, 3, 112, 112), NCHW format
        """
        import cv2

        # Resize to 112x112
        image = cv2.resize(image, (112, 112))

        # Convert RGB to BGR (ONNX model expects BGR)
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        # Normalize to [0, 1]
        image = image.astype(np.float32) / 255.0

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
