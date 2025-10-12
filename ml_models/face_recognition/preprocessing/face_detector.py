"""
Face Detection using MediaPipe
Fast, accurate, production-ready.
"""

from dataclasses import dataclass
from typing import cast

import mediapipe as mp
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
    MediaPipe-based face detector.
    Industry standard for production.
    """

    def __init__(self) -> None:
        self.config = FACE_DETECTION_CONFIG
        self.detector = mp.solutions.face_detection.FaceDetection(min_detection_confidence=self.config["min_detection_confidence"])

    def detect(self, image: np.ndarray) -> list[FaceDetection]:
        """
        Detect faces in image.

        Args:
            image: RGB image (HxWx3), uint8

        Returns:
            List of face detections, sorted by confidence
        """
        # Run detection
        results = self.detector.process(image)

        if not results.detections:
            return []

        # Convert to FaceDetection objects
        h, w = image.shape[:2]
        detections = []

        for detection in results.detections:
            bbox_rel = detection.location_data.relative_bounding_box

            # Convert relative to absolute coordinates
            x = int(bbox_rel.xmin * w)
            y = int(bbox_rel.ymin * h)
            width = int(bbox_rel.width * w)
            height = int(bbox_rel.height * h)

            # Validate minimum size
            min_face_size = cast(tuple[int, int], self.config["min_face_size"])
            min_w, min_h = min_face_size[0], min_face_size[1]
            if width < min_w or height < min_h:
                continue

            detections.append(FaceDetection(bbox=(x, y, width, height), confidence=detection.score[0]))

        # Sort by confidence (highest first)
        detections.sort(key=lambda d: d.confidence, reverse=True)

        # Limit to max_faces
        max_faces = cast(int, self.config["max_faces"])
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
        """Cleanup MediaPipe resources."""
        if hasattr(self, "detector"):
            self.detector.close()
