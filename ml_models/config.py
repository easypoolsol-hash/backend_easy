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
        "dimensions": 192,
        "enabled": True,
        "quality_threshold": 0.68,
        "description": "MobileFaceNet - Fast lightweight model (192D, 99.4% LFW)",
    },
    "arcface_int8": {
        "class": "ml_models.face_recognition.inference.arcface_int8.ArcFaceINT8",
        "dimensions": 512,
        "enabled": True,
        "quality_threshold": 0.70,
        "description": "ArcFace W600K - Banking-grade accuracy (512D, 99.82% LFW)",
    },
    "adaface": {
        "class": "ml_models.face_recognition.inference.adaface.AdaFace",
        "dimensions": 512,
        "enabled": False,  # DISABLED: ONNX model not available yet - download manually
        "quality_threshold": 0.65,
        "description": "AdaFace IR-101 - Quality-adaptive for varying conditions (512D, 99.4%+ LFW)",
    },
}

# Multi-model verification config
MULTI_MODEL_CONFIG = {
    "enabled": True,
    "models_for_verification": ["mobilefacenet", "arcface_int8"],  # 2 models (adaface disabled - no ONNX available)
    "consensus_strategy": "weighted",  # voting, weighted, unanimous
    "minimum_consensus": 2,  # Both models must agree (2-model mode)
}

# =============================================================================
# ENSEMBLE TUNING PARAMETERS (Adjustable for optimization)
# =============================================================================
ENSEMBLE_CONFIG = {
    # Model weights for weighted ensemble (must sum to 1.0)
    # 2-MODEL MODE: AdaFace disabled (no ONNX available)
    "model_weights": {
        "mobilefacenet": 0.50,  # Fast baseline, good for normal conditions
        "arcface_int8": 0.50,  # Banking-grade accuracy, good at distinguishing similar faces
        "adaface": 0.0,  # DISABLED - will be 0.30 when enabled
    },
    # Temperature scaling per model (adjusts score distribution)
    # Higher temperature = spread out scores, Lower = sharpen differences
    "temperature_scaling": {
        "mobilefacenet": {
            "enabled": False,  # MobileFaceNet scores are already well distributed
            "temperature": 1.0,
            "shift": 0.0,  # Shift scores before scaling
        },
        "arcface_int8": {
            "enabled": True,  # ArcFace W600K has compressed score range
            "temperature": 3.0,  # Spread out the 0.01-0.39 range
            "shift": -0.15,  # Center around 0.15 (typical score)
        },
        "adaface": {
            "enabled": False,  # AdaFace outputs well-distributed scores
            "temperature": 1.0,
            "shift": 0.0,
        },
    },
    # Per-model thresholds (override quality_threshold in FACE_RECOGNITION_MODELS)
    "thresholds": {
        "mobilefacenet": 0.50,  # Lower threshold for recall
        "arcface_int8": 0.25,  # Lower because scores are compressed
        "adaface": 0.40,
    },
    # Combined score thresholds for final decision
    "combined_thresholds": {
        "high_confidence": 0.55,  # Combined score >= this = HIGH confidence
        "medium_confidence": 0.40,  # Combined score >= this = MEDIUM confidence
        "match_threshold": 0.35,  # Minimum to consider a match
    },
    # Voting strategy parameters
    "voting": {
        "require_all_agree": False,  # If True, all models must agree for VERIFIED
        "minimum_agreeing": 1,  # Minimum models that must agree
        "use_weighted_vote": True,  # Weight votes by model confidence
    },
    # Score normalization (applied before temperature scaling)
    "normalization": {
        "clip_min": -1.0,  # Clip scores below this
        "clip_max": 1.0,  # Clip scores above this
        "apply_sigmoid": False,  # Apply sigmoid to normalize to 0-1 range
    },
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
