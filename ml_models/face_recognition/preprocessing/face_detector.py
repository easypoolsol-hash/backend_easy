"""
Face Detection using OpenCV DNN (ResNet-SSD)
Lightweight (~10MB), accurate (90-95%), production-ready.
Uses pre-trained ResNet-based face detection model.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np

from ml_models.config import FACE_DETECTION_CONFIG


@dataclass
class FaceDetection:
    """Face detection result."""

    bbox: tuple[int, int, int, int]  # x, y, width, height
    confidence: float
    landmarks: list | None = None


class FaceDetector:
    """
    OpenCV DNN face detector using ResNet-SSD.
    - Accurate: 90-95% detection rate (vs 70-80% for Haar)
    - Lightweight: ~10MB model files
    - Fast: Optimized for CPU inference
    - Robust: Handles angles, lighting, occlusions
    """

    def __init__(self) -> None:
        self.config = FACE_DETECTION_CONFIG
        self.net: Any = None  # Lazy load on first use (cv2 types not available)

    def _load_model(self) -> None:
        """Lazy load OpenCV DNN face detection model."""
        import cv2

        # Load ResNet-SSD model for face detection
        model_dir = Path(__file__).parent.parent / "models"
        model_path = model_dir / "res10_300x300_ssd_iter_140000.caffemodel"
        config_path = model_dir / "deploy.prototxt"

        if not model_path.exists() or not config_path.exists():
            raise FileNotFoundError(
                f"Face detection model files not found at {model_dir}. "
                f"Download from: https://github.com/opencv/opencv/tree/master/samples/dnn/face_detector"
            )

        self.net = cv2.dnn.readNetFromCaffe(str(config_path), str(model_path))  # type: ignore[assignment]

    def detect(self, image: np.ndarray) -> list[FaceDetection]:
        """
        Detect faces in image using DNN.

        Args:
            image: RGB image (HxWx3), uint8

        Returns:
            List of face detections, sorted by confidence (highest first)
        """
        # Lazy load model on first use
        if self.net is None:
            self._load_model()

        import cv2

        h, w = image.shape[:2]
        detections = []

        # Convert RGB to BGR for OpenCV
        image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        # Create blob and run detection
        blob = cv2.dnn.blobFromImage(image_bgr, 1.0, (300, 300), (104.0, 177.0, 123.0))
        self.net.setInput(blob)  # type: ignore[attr-defined]
        detections_dnn = self.net.forward()  # type: ignore[attr-defined]

        min_confidence = self.config.get("min_detection_confidence", 0.5)

        for i in range(detections_dnn.shape[2]):
            confidence = float(detections_dnn[0, 0, i, 2])

            if confidence > min_confidence:
                # Get bounding box coordinates
                box = detections_dnn[0, 0, i, 3:7] * np.array([w, h, w, h])
                x, y, x2, y2 = box.astype(int)
                width = x2 - x
                height = y2 - y

                # Validate minimum size
                min_face_size = cast(tuple[int, int], self.config.get("min_face_size", (30, 30)))
                if width < min_face_size[0] or height < min_face_size[1]:
                    continue

                detections.append(
                    FaceDetection(
                        bbox=(int(x), int(y), int(width), int(height)),
                        confidence=confidence,
                    )
                )

        # Sort by confidence (highest first)
        detections.sort(key=lambda d: d.confidence, reverse=True)

        # Limit to max_faces
        max_faces = cast(int, self.config.get("max_faces", 1))
        return detections[:max_faces]

    def crop_face(self, image: np.ndarray, detection: FaceDetection) -> np.ndarray:
        """
        Crop face from image with padding.

        Args:
            image: RGB image
            detection: Face detection result

        Returns:
            Cropped face image
        """
        x, y, w, h = detection.bbox

        # Add 10% padding
        padding = 0.1
        pad_w = int(w * padding)
        pad_h = int(h * padding)

        x1 = max(0, x - pad_w)
        y1 = max(0, y - pad_h)
        x2 = min(image.shape[1], x + w + pad_w)
        y2 = min(image.shape[0], y + h + pad_h)

        face_crop = image[y1:y2, x1:x2]
        return face_crop

    def __del__(self):
        """Cleanup resources."""
        self.net = None
