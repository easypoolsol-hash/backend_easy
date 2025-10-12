"""
ML Models Configuration
Centralized config for all machine learning models.
"""

from pathlib import Path

# Base paths
ML_MODELS_DIR = Path(__file__).parent
FACE_RECOGNITION_DIR = ML_MODELS_DIR / "face_recognition"
FACE_MODELS_DIR = FACE_RECOGNITION_DIR / "models"

# MobileFaceNet Configuration
MOBILEFACENET_CONFIG = {
    "model_path": FACE_MODELS_DIR / "mobilefacenet.tflite",
    "input_shape": (112, 112, 3),  # HxWxC
    "output_dims": 192,
    "input_range": (-1.0, 1.0),  # Normalized range
    "mean": [127.5, 127.5, 127.5],
    "std": [128.0, 128.0, 128.0],
}

# Face Detection Configuration
FACE_DETECTION_CONFIG = {
    "backend": "mediapipe",  # or 'mtcnn'
    "min_detection_confidence": 0.7,
    "min_face_size": (50, 50),  # pixels
    "max_faces": 1,
}

# Processing Configuration
PROCESSING_CONFIG = {
    "max_image_size": (1920, 1080),
    "jpeg_quality": 95,
    "timeout_seconds": 30,
    "max_faces_per_image": 1,  # Only process single face per photo
}

# Model Registry - maps model names to ML implementations
FACE_RECOGNITION_MODELS = {
    "mobilefacenet": {
        "class": "ml_models.face_recognition.inference.mobilefacenet.MobileFaceNet",
        "dimensions": MOBILEFACENET_CONFIG["output_dims"],
        "enabled": True,
        "quality_threshold": 0.7,
        "description": "MobileFaceNet - Matches frontend exactly (zero drift)",
    },
    # Add more models here in future
}

# Service-level config (business logic)
FACE_RECOGNITION_SERVICE_CONFIG = {
    "max_concurrent_processes": 2,
    "retry_attempts": 3,
    "embedding_batch_size": 10,
    "max_image_size_mb": 10,
    "max_faces_per_image": PROCESSING_CONFIG["max_faces_per_image"],
}

MODEL_LOADING_CONFIG = {
    "preload_enabled_models": True,
}
