"""
Image Service - Single Responsibility: Image Operations

Handles:
- Downloading images from GCS
- Converting image formats (bytes → numpy arrays)
- Loading multiple confirmation face crops
"""

import logging

import cv2
import numpy as np

from events.models import BoardingEvent

logger = logging.getLogger(__name__)


class ImageService:
    """Service for image loading and conversion operations"""

    @staticmethod
    def load_all_confirmation_faces(event: BoardingEvent) -> list[np.ndarray]:
        """
        Load ALL confirmation face crops from a boarding event

        Previously only used confirmation_face_1_gcs, now uses ALL 3 crops
        for better accuracy through multi-crop voting.

        Args:
            event: BoardingEvent with GCS paths for confirmation faces

        Returns:
            List of face images as RGB numpy arrays (one per crop)
        """
        from events.services.storage_service import BoardingEventStorageService

        storage = BoardingEventStorageService()
        face_images = []

        # Try to load all 3 confirmation face crops
        gcs_paths = [event.confirmation_face_1_gcs, event.confirmation_face_2_gcs, event.confirmation_face_3_gcs]

        for i, gcs_path in enumerate(gcs_paths, start=1):
            if not gcs_path:
                logger.debug(f"Event {event.event_id}: confirmation_face_{i}_gcs is empty, skipping")
                continue

            try:
                face_image = ImageService._download_and_convert_image(storage, gcs_path)
                face_images.append(face_image)
                logger.info(f"Event {event.event_id}: Loaded confirmation face crop {i}")
            except Exception as e:
                logger.error(f"Event {event.event_id}: Failed to load crop {i} from {gcs_path}: {e}")
                # Continue with other crops

        if not face_images:
            raise ValueError(f"No confirmation faces could be loaded for event {event.event_id}")

        logger.info(f"Event {event.event_id}: Successfully loaded {len(face_images)}/3 confirmation face crops")
        return face_images

    @staticmethod
    def _download_and_convert_image(storage, gcs_path: str) -> np.ndarray:
        """
        Download image from GCS and convert to RGB numpy array

        Args:
            storage: BoardingEventStorageService instance
            gcs_path: GCS path to image file

        Returns:
            RGB numpy array (height, width, 3)
        """
        # Download image bytes from GCS
        image_bytes = storage.download_image(gcs_path)

        # Decode image bytes to numpy array (BGR format)
        image_bgr = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)

        if image_bgr is None:
            raise ValueError(f"Failed to decode image from {gcs_path}")

        # Convert BGR to RGB (models expect RGB)
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

        return image_rgb
