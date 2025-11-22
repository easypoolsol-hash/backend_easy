"""
Model Loader for Cloud Run
Downloads ML models from Google Cloud Storage to local container storage on startup.
Now reads model configuration from database (FaceRecognitionModel).
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class ModelLoader:
    """
    Downloads face recognition models from GCS to local storage.
    Reads enabled models from database (FaceRecognitionModel).
    Should be called once during Cloud Run container startup.
    """

    def __init__(
        self,
        local_models_dir: str | None = None,
    ):
        """
        Initialize the model loader.

        Args:
            local_models_dir: Local directory to download models to.
                            Defaults to ml_models/face_recognition/models/
        """
        if local_models_dir is None:
            # Default to the face_recognition models directory
            self.local_models_dir = Path(__file__).parent / "face_recognition" / "models"
        else:
            self.local_models_dir = Path(local_models_dir)

        self.local_models_dir.mkdir(parents=True, exist_ok=True)

    def get_models_from_database(self) -> list[dict]:
        """
        Get enabled models from database.
        Falls back to hardcoded defaults if database not available.
        """
        try:
            from ml_config.models import FaceRecognitionModel

            enabled_models = FaceRecognitionModel.get_enabled_models()

            if not enabled_models.exists():
                logger.warning("No enabled models in database, creating defaults...")
                FaceRecognitionModel.create_default_models()
                enabled_models = FaceRecognitionModel.get_enabled_models()

            models = []
            for model in enabled_models:
                models.append(
                    {
                        "name": model.name,
                        "filename": model.local_filename,
                        "gcs_bucket": model.gcs_bucket,
                        "gcs_path": model.gcs_path,
                        "size_mb": model.file_size_mb,
                    }
                )

            logger.info(f"Loaded {len(models)} models from database: {[m['name'] for m in models]}")
            return models

        except Exception as e:
            logger.warning(f"Cannot load models from database: {e}. Using hardcoded defaults.")
            # Fallback to hardcoded defaults
            return [
                {
                    "name": "mobilefacenet",
                    "filename": "mobilefacenet.tflite",
                    "gcs_bucket": "easypool-ml-models",
                    "gcs_path": "face-recognition/v1/mobilefacenet.tflite",
                    "size_mb": 5,
                },
                {
                    "name": "arcface_int8",
                    "filename": "arcface_int8.onnx",
                    "gcs_bucket": "easypool-ml-models",
                    "gcs_path": "face-recognition/v1/arcface_int8.onnx",
                    "size_mb": 63,
                },
            ]

    def model_exists_locally(self, filename: str) -> bool:
        """Check if model already exists in local storage."""
        local_path = self.local_models_dir / filename
        return local_path.exists() and local_path.stat().st_size > 0

    def download_model(self, model: dict[str, str]) -> bool:
        """
        Download a single model from GCS to local storage.

        Args:
            model: Dictionary with 'filename', 'gcs_path', 'gcs_bucket', and 'size_mb'

        Returns:
            True if download succeeded, False otherwise
        """
        from google.cloud import storage

        filename = model["filename"]
        gcs_bucket = model.get("gcs_bucket", "easypool-ml-models")
        gcs_path = model["gcs_path"]
        size_mb = model.get("size_mb", 0)
        local_path = self.local_models_dir / filename

        # Skip if already exists
        if self.model_exists_locally(filename):
            logger.info(f"[SKIP] Model already exists: {filename}")
            return True

        try:
            logger.info(f"[DOWNLOADING] {filename} ({size_mb} MB) from gs://{gcs_bucket}/{gcs_path}...")

            storage_client = storage.Client()
            bucket = storage_client.bucket(gcs_bucket)
            blob = bucket.blob(gcs_path)

            # Download to local file
            blob.download_to_filename(str(local_path))

            # Verify download
            if not local_path.exists() or local_path.stat().st_size == 0:
                logger.error(f"[ERROR] Download failed: {filename} (file missing or empty)")
                return False

            logger.info(f"[OK] Downloaded: {filename} ({local_path.stat().st_size / (1024 * 1024):.1f} MB)")
            return True

        except Exception as e:
            logger.error(f"[ERROR] Failed to download {filename}: {e!s}")
            return False

    def download_all_models(self) -> dict[str, bool]:
        """
        Download all enabled models from GCS to local storage.
        Reads model list from database (FaceRecognitionModel).

        Returns:
            Dictionary mapping filename to download success status
        """
        # Get models from database
        models = self.get_models_from_database()

        logger.info("=" * 70)
        logger.info("ML Models Download from Google Cloud Storage")
        logger.info(f"Local directory: {self.local_models_dir}")
        logger.info("=" * 70)

        results = {}
        total_size_mb = sum(model.get("size_mb", 0) for model in models)

        logger.info(f"Total models to download: {len(models)} ({total_size_mb} MB)")

        for model in models:
            success = self.download_model(model)
            results[model["filename"]] = success

        # Summary
        logger.info("=" * 70)
        successful = sum(1 for success in results.values() if success)
        logger.info(f"Download complete: {successful}/{len(models)} models ready")

        if successful < len(models):
            logger.warning("Some models failed to download. Face verification may not work correctly.")
        else:
            logger.info("All models downloaded successfully")

        logger.info("=" * 70)

        return results

    def verify_models_ready(self) -> bool:
        """
        Verify that all required models are present locally.

        Returns:
            True if all models are ready, False otherwise
        """
        models = self.get_models_from_database()
        all_present = all(self.model_exists_locally(model["filename"]) for model in models)

        if not all_present:
            missing = [model["filename"] for model in models if not self.model_exists_locally(model["filename"])]
            logger.error(f"Missing models: {missing}")

        return all_present


def load_models_on_startup():
    """
    Convenience function to download models on Cloud Run startup.
    Call this from your application's __main__ or startup script.

    Example:
        if __name__ == "__main__":
            from ml_models.model_loader import load_models_on_startup
            load_models_on_startup()
            # Then start your FastAPI/Flask app
    """
    loader = ModelLoader()

    # Check if running on Cloud Run (has GCS access)
    is_cloud_run = os.getenv("K_SERVICE") is not None

    if is_cloud_run:
        logger.info("Running on Cloud Run - downloading models from GCS...")
        loader.download_all_models()

        if not loader.verify_models_ready():
            logger.error("❌ Not all models are ready. Application may not function correctly.")
            # Don't fail startup - allow app to start but log the error
            # Face verification will fail gracefully when models are missing
        else:
            logger.info("✅ All models loaded successfully")
    else:
        logger.info("Not running on Cloud Run - using local models")
        if not loader.verify_models_ready():
            logger.warning("⚠️  Some models missing locally. Run download_onnx_models.py to download models for local development.")


if __name__ == "__main__":
    # Test the model loader
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    load_models_on_startup()
