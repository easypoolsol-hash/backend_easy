"""
AdaFace IR-101 WebFace12M ONNX Inference
Quality-adaptive face recognition - automatically adjusts to image quality
Best for varying lighting conditions, blur, occlusion, and low-quality images

Key Features:
- Adaptive feature norm based on image quality
- Robust to lighting variations (morning, evening, shadows)
- Handles motion blur and partial occlusions
- Trained on 12M faces for excellent generalization
- 512-dimensional embeddings
"""

from pathlib import Path

import numpy as np

from .base import BaseFaceRecognitionModel


class AdaFace(BaseFaceRecognitionModel):
    """
    AdaFace with IR-101 backbone - Quality-adaptive face recognition.
    Automatically adjusts feature extraction based on detected image quality.
    Perfect for real-world scenarios with varying conditions.

    Model: adaface_ir101_webface12m.onnx
    Size: ~250MB
    Accuracy: 99.4%+ LFW
    Embeddings: 512D
    """

    def __init__(self):
        model_path = Path(__file__).parent.parent / "models" / "adaface_ir101_webface12m.onnx"
        super().__init__(model_path)
        self.session = None  # Lazy loaded ONNX session

    def _validate_model(self) -> None:
        """Validate that AdaFace model exists"""
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"AdaFace model not found at {self.model_path}\n"
                f"Download from: https://github.com/mk-minchul/AdaFace/releases/download/v1.0/adaface_ir101_webface12m.onnx\n"
                f"Or run: gsutil cp gs://easypool-ml-models/face-recognition/v1/adaface_ir101_webface12m.onnx {self.model_path}"
            )

    def _load_model(self) -> None:
        """Load AdaFace ONNX model"""
        import onnxruntime as ort

        self.session = ort.InferenceSession(str(self.model_path), providers=["CPUExecutionProvider"])

        # Verify input/output shapes
        input_shape = self.session.get_inputs()[0].shape
        output_shape = self.session.get_outputs()[0].shape

        if input_shape != [1, 3, 112, 112]:
            raise ValueError(f"Expected input shape [1, 3, 112, 112], got {input_shape}")
        if output_shape[1] != 512:
            raise ValueError(f"Expected 512D embeddings, got {output_shape[1]}D")

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess face image for AdaFace model.

        Args:
            image: RGB numpy array (H, W, 3)

        Returns:
            Preprocessed image ready for model (1, 3, 112, 112)
        """
        import cv2

        # Resize to 112x112
        image = cv2.resize(image, (112, 112), interpolation=cv2.INTER_LINEAR)

        # AdaFace preprocessing (same as ArcFace):
        # Normalize: (pixel - 127.5) / 128.0 = range [-1, 1]
        image = image.astype(np.float32)
        image = (image - 127.5) / 128.0

        # Transpose from HWC to CHW format (ONNX uses NCHW)
        image = np.transpose(image, (2, 0, 1))

        # Add batch dimension
        image = np.expand_dims(image, axis=0)

        return image

    def get_embedding(self, face_image: np.ndarray) -> np.ndarray:
        """
        Extract 512D embedding from face image using AdaFace.
        Quality-adaptive - automatically adjusts based on image quality.

        Args:
            face_image: RGB numpy array (H, W, 3)

        Returns:
            512D embedding as numpy array
        """
        if self.session is None:
            self._load_model()

        # Preprocess image
        input_image = self.preprocess(face_image)

        # Run inference
        input_name = self.session.get_inputs()[0].name
        output_name = self.session.get_outputs()[0].name
        embedding = self.session.run([output_name], {input_name: input_image})[0]

        # AdaFace outputs normalized embeddings (L2 normalized)
        # Feature norm is adaptive based on quality
        embedding = embedding.flatten()

        # Additional L2 normalization (ensure unit norm)
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding
