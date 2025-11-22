"""
ML Configuration Models
Dynamic backend model configuration for face recognition ensemble.
"""

from django.core.exceptions import ValidationError
from django.db import models


class FaceRecognitionModel(models.Model):
    """
    Individual face recognition model configuration.
    Each model (MobileFaceNet, ArcFace, W600K, etc.) is a separate entry.

    Configure models from Django Admin:
    - Enable/disable models
    - Set GCS paths for auto-download
    - Configure weights, thresholds, temperature scaling
    """

    # Identification
    name = models.CharField(max_length=100, unique=True, help_text="Internal name (e.g., 'mobilefacenet', 'w600k_r50')")
    display_name = models.CharField(max_length=255, help_text="Display name (e.g., 'MobileFaceNet', 'W600K ResNet50')")

    # GCS Configuration
    gcs_bucket = models.CharField(max_length=255, default="easypool-ml-models", help_text="GCS bucket name")
    gcs_path = models.CharField(max_length=500, help_text="Path in GCS (e.g., 'face-recognition/v1/w600k_r50.onnx')")
    local_filename = models.CharField(max_length=255, help_text="Local filename (e.g., 'w600k_r50.onnx')")
    file_size_mb = models.IntegerField(default=0, help_text="Approximate file size in MB (for progress indication)")

    # Model State
    is_enabled = models.BooleanField(default=True, help_text="Enable this model for verification")

    # Model Parameters
    weight = models.FloatField(default=0.33, help_text="Weight in ensemble (0.0 - 1.0). All enabled models' weights should sum to 1.0")
    threshold = models.FloatField(default=0.40, help_text="Minimum similarity score to consider a match (0.0 - 1.0)")

    # Temperature Scaling
    temperature_enabled = models.BooleanField(default=False, help_text="Enable temperature scaling for this model")
    temperature = models.FloatField(default=1.0, help_text="Temperature value (higher = spread out scores)")
    shift = models.FloatField(default=0.0, help_text="Shift scores before scaling")

    # Inference Configuration
    inference_class = models.CharField(
        max_length=500, help_text="Full path to inference class (e.g., 'ml_models.face_recognition.inference.w600k_r50.W600KModel')"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Face Recognition Model"
        verbose_name_plural = "Face Recognition Models"

    def __str__(self):
        status = "ON" if self.is_enabled else "OFF"
        return f"{self.display_name} [{status}] (weight={self.weight:.2f})"

    def clean(self):
        """Validate model parameters"""
        errors = {}

        if not (0 <= self.weight <= 1):
            errors["weight"] = "Weight must be between 0.0 and 1.0"

        if not (0 <= self.threshold <= 1):
            errors["threshold"] = "Threshold must be between 0.0 and 1.0"

        if self.temperature_enabled and self.temperature <= 0:
            errors["temperature"] = "Temperature must be positive"

        if errors:
            raise ValidationError(errors)

    def to_dict(self):
        """Convert to dictionary for consensus service"""
        return {
            "name": self.name,
            "weight": self.weight,
            "threshold": self.threshold,
            "temperature_scaling": {
                "enabled": self.temperature_enabled,
                "temperature": self.temperature,
                "shift": self.shift,
            },
            "gcs_bucket": self.gcs_bucket,
            "gcs_path": self.gcs_path,
            "local_filename": self.local_filename,
            "inference_class": self.inference_class,
        }

    @classmethod
    def get_enabled_models(cls):
        """Get all enabled models"""
        return cls.objects.filter(is_enabled=True)

    @classmethod
    def create_default_models(cls):
        """Create default model configurations"""
        defaults = [
            {
                "name": "mobilefacenet",
                "display_name": "MobileFaceNet",
                "gcs_path": "face-recognition/v1/mobilefacenet.tflite",
                "local_filename": "mobilefacenet.tflite",
                "file_size_mb": 5,
                "is_enabled": True,
                "weight": 0.35,
                "threshold": 0.50,
                "temperature_enabled": False,
                "temperature": 1.0,
                "shift": 0.0,
                "inference_class": "ml_models.face_recognition.inference.mobilefacenet.MobileFaceNetModel",
            },
            {
                "name": "arcface_int8",
                "display_name": "ArcFace INT8",
                "gcs_path": "face-recognition/v1/arcface_int8.onnx",
                "local_filename": "arcface_int8.onnx",
                "file_size_mb": 63,
                "is_enabled": True,
                "weight": 0.35,
                "threshold": 0.25,
                "temperature_enabled": True,
                "temperature": 3.0,
                "shift": -0.15,
                "inference_class": "ml_models.face_recognition.inference.arcface_int8.ArcFaceINT8Model",
            },
            {
                "name": "w600k_r50",
                "display_name": "W600K ResNet50",
                "gcs_path": "face-recognition/v1/w600k_r50.onnx",
                "local_filename": "w600k_r50.onnx",
                "file_size_mb": 174,
                "is_enabled": True,
                "weight": 0.30,
                "threshold": 0.40,
                "temperature_enabled": False,
                "temperature": 1.0,
                "shift": 0.0,
                "inference_class": "ml_models.face_recognition.inference.w600k_r50.W600KModel",
            },
        ]

        created = []
        for model_data in defaults:
            model, was_created = cls.objects.get_or_create(name=model_data["name"], defaults=model_data)
            if was_created:
                created.append(model.name)

        return created


class BackendModelConfiguration(models.Model):
    """
    Dynamic configuration for backend face recognition 3-model ensemble.
    Allows tuning ML parameters without code deployment.

    Only ONE configuration can be active at a time.
    Each boarding event stores which config version was used for verification.
    Old results remain unchanged (tied to their config version).
    """

    # Metadata
    version = models.IntegerField(unique=True, help_text="Config version number (auto-incremented)")
    name = models.CharField(max_length=255, help_text="Descriptive name (e.g., 'Production V1', 'High Accuracy Tuning')")
    description = models.TextField(blank=True, help_text="What changed in this configuration")
    is_active = models.BooleanField(default=False, help_text="Only one config can be active at a time")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # =============================================================================
    # MODEL WEIGHTS (must sum to 1.0)
    # =============================================================================
    mobilefacenet_weight = models.FloatField(default=0.35, help_text="Weight for MobileFaceNet (0.0 - 1.0). Fast, good for normal conditions.")
    arcface_weight = models.FloatField(default=0.35, help_text="Weight for ArcFace W600K (0.0 - 1.0). Banking-grade accuracy.")
    adaface_weight = models.FloatField(default=0.30, help_text="Weight for AdaFace (0.0 - 1.0). Quality-adaptive, handles difficult lighting.")

    # =============================================================================
    # PER-MODEL THRESHOLDS
    # =============================================================================
    mobilefacenet_threshold = models.FloatField(default=0.50, help_text="Minimum similarity score for MobileFaceNet to consider a match (0.0 - 1.0)")
    arcface_threshold = models.FloatField(
        default=0.25, help_text="Minimum similarity score for ArcFace (0.0 - 1.0). Lower because scores are compressed."
    )
    adaface_threshold = models.FloatField(default=0.40, help_text="Minimum similarity score for AdaFace (0.0 - 1.0)")

    # =============================================================================
    # COMBINED SCORE THRESHOLDS (Banking-Grade Standards)
    # =============================================================================
    high_confidence_threshold = models.FloatField(default=0.60, help_text="Combined score >= this = HIGH confidence match (FAR < 0.1%)")
    medium_confidence_threshold = models.FloatField(default=0.45, help_text="Combined score >= this = MEDIUM confidence match")
    match_threshold = models.FloatField(default=0.35, help_text="Minimum combined score to consider a match (below this = NO MATCH)")

    # =============================================================================
    # CONSENSUS STRATEGY
    # =============================================================================
    minimum_consensus = models.IntegerField(default=2, help_text="Minimum number of models that must agree (1-3)")
    require_all_agree = models.BooleanField(default=False, help_text="If True, all 3 models must agree for VERIFIED status")
    use_weighted_vote = models.BooleanField(default=True, help_text="If True, use model weights when voting. If False, each model gets equal vote.")

    # =============================================================================
    # TEMPERATURE SCALING
    # =============================================================================
    # MobileFaceNet temperature scaling
    mobilefacenet_temperature_enabled = models.BooleanField(default=False, help_text="Enable temperature scaling for MobileFaceNet")
    mobilefacenet_temperature = models.FloatField(default=1.0, help_text="Temperature value (higher = spread out scores)")
    mobilefacenet_shift = models.FloatField(default=0.0, help_text="Shift scores before scaling")

    # ArcFace temperature scaling
    arcface_temperature_enabled = models.BooleanField(default=True, help_text="Enable temperature scaling for ArcFace (recommended)")
    arcface_temperature = models.FloatField(default=3.0, help_text="Temperature value (ArcFace scores are compressed, need spreading)")
    arcface_shift = models.FloatField(default=-0.15, help_text="Shift scores before scaling (center around typical score)")

    # AdaFace temperature scaling
    adaface_temperature_enabled = models.BooleanField(default=False, help_text="Enable temperature scaling for AdaFace")
    adaface_temperature = models.FloatField(default=1.0, help_text="Temperature value")
    adaface_shift = models.FloatField(default=0.0, help_text="Shift scores before scaling")

    class Meta:
        ordering = ["-version"]
        verbose_name = "Backend Model Configuration"
        verbose_name_plural = "Backend Model Configurations"

    def __str__(self):
        active_status = "🟢 ACTIVE" if self.is_active else ""
        return f"V{self.version}: {self.name} {active_status}"

    def clean(self):
        """Validate configuration parameters"""
        errors = {}

        # Validate weights sum to 1.0 (allow small floating point error)
        total_weight = self.mobilefacenet_weight + self.arcface_weight + self.adaface_weight
        if abs(total_weight - 1.0) > 0.001:
            errors["__all__"] = f"Model weights must sum to 1.0 (currently: {total_weight:.3f})"

        # Validate individual weights are in [0, 1]
        if not (0 <= self.mobilefacenet_weight <= 1):
            errors["mobilefacenet_weight"] = "Weight must be between 0.0 and 1.0"
        if not (0 <= self.arcface_weight <= 1):
            errors["arcface_weight"] = "Weight must be between 0.0 and 1.0"
        if not (0 <= self.adaface_weight <= 1):
            errors["adaface_weight"] = "Weight must be between 0.0 and 1.0"

        # Validate thresholds are in [0, 1]
        thresholds = {
            "mobilefacenet_threshold": self.mobilefacenet_threshold,
            "arcface_threshold": self.arcface_threshold,
            "adaface_threshold": self.adaface_threshold,
            "high_confidence_threshold": self.high_confidence_threshold,
            "medium_confidence_threshold": self.medium_confidence_threshold,
            "match_threshold": self.match_threshold,
        }
        for field_name, value in thresholds.items():
            if not (0 <= value <= 1):
                errors[field_name] = "Threshold must be between 0.0 and 1.0"

        # Validate threshold hierarchy: high > medium > match
        if self.high_confidence_threshold < self.medium_confidence_threshold:
            errors["high_confidence_threshold"] = "High confidence threshold must be >= medium confidence threshold"
        if self.medium_confidence_threshold < self.match_threshold:
            errors["medium_confidence_threshold"] = "Medium confidence threshold must be >= match threshold"

        # Validate minimum_consensus is 1-3
        if not (1 <= self.minimum_consensus <= 3):
            errors["minimum_consensus"] = "Minimum consensus must be between 1 and 3"

        # Validate temperature values are positive
        if self.mobilefacenet_temperature_enabled and self.mobilefacenet_temperature <= 0:
            errors["mobilefacenet_temperature"] = "Temperature must be positive"
        if self.arcface_temperature_enabled and self.arcface_temperature <= 0:
            errors["arcface_temperature"] = "Temperature must be positive"
        if self.adaface_temperature_enabled and self.adaface_temperature <= 0:
            errors["adaface_temperature"] = "Temperature must be positive"

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Auto-increment version and ensure only one active config"""
        # Auto-increment version for new configs
        if not self.pk and not self.version:
            last_config = BackendModelConfiguration.objects.order_by("-version").first()
            self.version = (last_config.version + 1) if last_config else 1

        # If setting this config as active, deactivate all others
        if self.is_active:
            BackendModelConfiguration.objects.filter(is_active=True).update(is_active=False)

        # Run validation
        self.full_clean()

        super().save(*args, **kwargs)

    def to_dict(self):
        """
        Convert configuration to dictionary format for consensus_service.
        Returns format compatible with existing ENSEMBLE_CONFIG in ml_models/config.py
        """
        return {
            "model_weights": {
                "mobilefacenet": self.mobilefacenet_weight,
                "arcface_int8": self.arcface_weight,
                "adaface": self.adaface_weight,
            },
            "temperature_scaling": {
                "mobilefacenet": {
                    "enabled": self.mobilefacenet_temperature_enabled,
                    "temperature": self.mobilefacenet_temperature,
                    "shift": self.mobilefacenet_shift,
                },
                "arcface_int8": {
                    "enabled": self.arcface_temperature_enabled,
                    "temperature": self.arcface_temperature,
                    "shift": self.arcface_shift,
                },
                "adaface": {
                    "enabled": self.adaface_temperature_enabled,
                    "temperature": self.adaface_temperature,
                    "shift": self.adaface_shift,
                },
            },
            "thresholds": {
                "mobilefacenet": self.mobilefacenet_threshold,
                "arcface_int8": self.arcface_threshold,
                "adaface": self.adaface_threshold,
            },
            "combined_thresholds": {
                "high_confidence": self.high_confidence_threshold,
                "medium_confidence": self.medium_confidence_threshold,
                "match_threshold": self.match_threshold,
            },
            "voting": {
                "require_all_agree": self.require_all_agree,
                "minimum_agreeing": self.minimum_consensus,
                "use_weighted_vote": self.use_weighted_vote,
            },
        }

    @classmethod
    def get_active_config(cls):
        """Get the currently active configuration"""
        config = cls.objects.filter(is_active=True).first()
        if not config:
            # Create default config if none exists
            config = cls.create_default_config()
        return config

    @classmethod
    def create_default_config(cls):
        """Create default configuration matching current ml_models/config.py (2-model mode)"""
        config = cls.objects.create(
            name="Default 2-Model Config (MobileFaceNet + ArcFace)",
            description="2-model consensus: AdaFace disabled (ONNX not available). Both models must agree.",
            is_active=True,
            # Weights (2-model mode: 50-50 split)
            mobilefacenet_weight=0.50,
            arcface_weight=0.50,
            adaface_weight=0.0,  # DISABLED
            # Per-model thresholds
            mobilefacenet_threshold=0.50,
            arcface_threshold=0.25,
            adaface_threshold=0.40,
            # Combined thresholds (banking-grade standards)
            high_confidence_threshold=0.60,  # Banking-grade: FAR < 0.1%
            medium_confidence_threshold=0.45,
            match_threshold=0.35,
            # Consensus (2-model mode: both must agree)
            minimum_consensus=2,
            require_all_agree=True,  # In 2-model mode, both must agree
            use_weighted_vote=True,
            # Temperature scaling
            mobilefacenet_temperature_enabled=False,
            mobilefacenet_temperature=1.0,
            mobilefacenet_shift=0.0,
            arcface_temperature_enabled=True,
            arcface_temperature=3.0,
            arcface_shift=-0.15,
            adaface_temperature_enabled=False,
            adaface_temperature=1.0,
            adaface_shift=0.0,
        )
        return config
