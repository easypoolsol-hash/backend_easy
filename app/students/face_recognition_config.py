"""
Face Recognition Model Configuration
DRY: Imports from ml_models (Single Source of Truth)
"""

from ml_models.config import (
    MOBILEFACENET_CONFIG,
    FACE_DETECTION_CONFIG,
    PROCESSING_CONFIG,
)

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
FACE_RECOGNITION_CONFIG = {
    "max_concurrent_processes": 2,
    "retry_attempts": 3,
    "embedding_batch_size": 10,
    "max_image_size_mb": PROCESSING_CONFIG["max_image_size"][0] * PROCESSING_CONFIG["max_image_size"][1] / (1024 * 1024),
    "max_faces_per_image": PROCESSING_CONFIG["max_faces_per_image"],
}

MODEL_LOADING_CONFIG = {
    "preload_enabled_models": True,
}


def get_enabled_models():
    """Get only enabled models from configuration."""
    return {name: config for name, config in FACE_RECOGNITION_MODELS.items() if config["enabled"]}


def get_model_config(model_name: str):
    """Get configuration for a specific model."""
    if model_name not in FACE_RECOGNITION_MODELS:
        raise ValueError(f"Unknown model: {model_name}")
    return FACE_RECOGNITION_MODELS[model_name]


def get_model_dimensions(model_name: str) -> int:
    """Get embedding dimensions for a model."""
    return get_model_config(model_name)["dimensions"]


def validate_model_config():
    """Validate the model configuration for consistency."""
    errors = []

    enabled_models = get_enabled_models()
    if not enabled_models:
        errors.append("No models are enabled")

    for name, config in FACE_RECOGNITION_MODELS.items():
        # Check required fields
        required_fields = ["class", "dimensions", "enabled", "quality_threshold"]
        for field in required_fields:
            if field not in config:
                errors.append(f"Model {name}: missing required field '{field}'")

        # Validate dimensions
        if "dimensions" in config and not isinstance(config["dimensions"], int):
            errors.append(f"Model {name}: dimensions must be an integer")

        # Validate quality threshold
        if "quality_threshold" in config:
            threshold = config["quality_threshold"]
            if not (0.0 <= threshold <= 1.0):
                errors.append(f"Model {name}: quality_threshold must be between 0.0 and 1.0")

    return errors


# Validate configuration on import
config_errors = validate_model_config()
if config_errors:
    raise ValueError(f"Model configuration errors: {config_errors}")
