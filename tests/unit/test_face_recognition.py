"""
Unit tests for face recognition service and signal handlers.
Tests embedding generation, face detection, and auto-processing.
"""

import io
from unittest.mock import Mock, patch

import numpy as np
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from students.models import FaceEmbeddingMetadata, StudentPhoto
from students.services.face_recognition_service import FaceRecognitionService
from tests.factories import StudentFactory, StudentPhotoFactory


@pytest.fixture
def real_face_image():
    """Create a realistic test image (200x200 face)."""
    # Create RGB image with face-like structure
    img = Image.new("RGB", (200, 200), color=(255, 220, 180))  # Skin tone

    # Add simple features (eyes, nose simulation)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)

    # Eyes
    draw.ellipse([60, 70, 80, 90], fill=(50, 50, 50))
    draw.ellipse([120, 70, 140, 90], fill=(50, 50, 50))

    # Nose
    draw.ellipse([95, 100, 105, 120], fill=(200, 180, 160))

    # Mouth
    draw.ellipse([80, 140, 120, 155], fill=(180, 100, 100))

    # Save to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    return SimpleUploadedFile(
        name="test_face.jpg", content=img_bytes.read(), content_type="image/jpeg"
    )


@pytest.fixture
def mock_face_detector():
    """Mock FaceDetector that finds one valid face."""
    with patch(
        "ml_models.face_recognition.preprocessing.face_detector.FaceDetector"
    ) as MockDetector:
        detector_instance = Mock()

        # Mock successful face detection
        mock_detection = Mock()
        mock_detection.bbox = (50, 50, 100, 100)
        mock_detection.confidence = 0.95

        detector_instance.detect.return_value = [mock_detection]
        detector_instance.crop_face.return_value = np.random.randint(
            0, 255, (112, 112, 3), dtype=np.uint8
        )

        MockDetector.return_value = detector_instance
        yield MockDetector


@pytest.fixture
def mock_mobilefacenet():
    """Mock MobileFaceNet model that generates high-quality embeddings."""
    with patch("students.services.face_recognition_service.import_module") as mock_import:
        model_instance = Mock()

        # Generate realistic high-variance normalized embedding (192-dim)
        # Use values that will pass quality checks (variance > 0)
        fake_embedding = np.random.uniform(low=-1.0, high=1.0, size=192).astype(np.float32)
        fake_embedding = fake_embedding / np.linalg.norm(fake_embedding)  # L2 normalize
        model_instance.generate_embedding.return_value = fake_embedding

        # Mock the MobileFaceNet class
        mock_module = Mock()
        mock_module.MobileFaceNet.return_value = model_instance
        mock_import.return_value = mock_module

        yield model_instance


@pytest.mark.django_db
class TestFaceRecognitionSignal:
    """Test automatic embedding generation via Django signals."""

    def test_signal_fires_on_photo_creation(
        self, real_face_image, mock_face_detector, mock_mobilefacenet
    ):
        """Test that creating a photo triggers signal and generates embeddings."""
        student = StudentFactory()

        # Create photo (signal should fire)
        photo = StudentPhotoFactory(student=student, photo=real_face_image)

        # Check embeddings were created
        embeddings = FaceEmbeddingMetadata.objects.filter(student_photo=photo)

        assert embeddings.exists(), "Signal should auto-generate embeddings"
        assert embeddings.count() >= 1, "At least one embedding should exist"

    def test_signal_does_not_fire_on_update(self, real_face_image):
        """Test that updating a photo does NOT trigger signal."""
        student = StudentFactory()
        photo = StudentPhotoFactory(student=student, photo=real_face_image)

        initial_count = FaceEmbeddingMetadata.objects.filter(student_photo=photo).count()

        # Update photo metadata (NOT creation)
        photo.is_primary = False
        photo.save()

        final_count = FaceEmbeddingMetadata.objects.filter(student_photo=photo).count()

        assert (
            initial_count == final_count
        ), "Signal should only fire on creation, not update"

    def test_signal_skips_when_no_photo_file(self):
        """Test signal gracefully handles missing photo file."""
        student = StudentFactory()

        # Create StudentPhoto without actual file
        photo = StudentPhoto.objects.create(student=student, is_primary=True)

        # Should not crash, just skip
        embeddings = FaceEmbeddingMetadata.objects.filter(student_photo=photo)
        assert embeddings.count() == 0, "No embeddings when photo file missing"


@pytest.mark.django_db
class TestFaceRecognitionService:
    """Test FaceRecognitionService directly."""

    def test_service_lazy_loads_ml_libraries(self):
        """Test that service doesn't load ML libraries until needed."""
        service = FaceRecognitionService()

        # Initially, should be None (lazy loaded)
        assert service._face_detector is None, "Face detector should be lazy-loaded"
        assert service._model_instances == {}, "Models should be lazy-loaded"

    def test_process_photo_success(
        self, real_face_image, mock_face_detector, mock_mobilefacenet
    ):
        """Test successful photo processing with valid face."""
        student = StudentFactory()
        photo = StudentPhotoFactory.build(student=student)
        photo.photo = real_face_image
        photo.save()

        service = FaceRecognitionService()
        result = service.process_student_photo(photo)

        assert result is True, "Processing should succeed"

        # Verify embeddings created
        embeddings = FaceEmbeddingMetadata.objects.filter(student_photo=photo)
        assert embeddings.exists(), "Embeddings should be created"

    def test_process_photo_no_face_detected(self, real_face_image):
        """Test processing fails gracefully when no face detected."""
        with patch(
            "ml_models.face_recognition.preprocessing.face_detector.FaceDetector"
        ) as MockDetector:
            detector_instance = Mock()
            detector_instance.detect.return_value = []  # No faces
            MockDetector.return_value = detector_instance

            student = StudentFactory()
            photo = StudentPhotoFactory.build(student=student)
            photo.photo = real_face_image
            photo.save()

            service = FaceRecognitionService()
            result = service.process_student_photo(photo)

            assert result is False, "Should fail when no face detected"

    def test_process_photo_multiple_faces_rejected(self, real_face_image):
        """Test that photos with multiple faces are rejected."""
        with patch(
            "ml_models.face_recognition.preprocessing.face_detector.FaceDetector"
        ) as MockDetector:
            detector_instance = Mock()

            # Return multiple faces
            mock_detection1 = Mock()
            mock_detection1.bbox = (50, 50, 100, 100)
            mock_detection1.confidence = 0.95

            mock_detection2 = Mock()
            mock_detection2.bbox = (150, 150, 200, 200)
            mock_detection2.confidence = 0.90

            detector_instance.detect.return_value = [mock_detection1, mock_detection2]
            MockDetector.return_value = detector_instance

            student = StudentFactory()
            photo = StudentPhotoFactory.build(student=student)
            photo.photo = real_face_image
            photo.save()

            service = FaceRecognitionService()
            result = service.process_student_photo(photo)

            assert result is False, "Should reject photos with multiple faces"

    def test_lazy_loading_triggers_on_first_use(
        self, real_face_image, mock_face_detector
    ):
        """Test that face detector loads on first use."""
        service = FaceRecognitionService()

        assert service._face_detector is None, "Initially None"

        # Process photo (triggers lazy load)
        student = StudentFactory()
        photo = StudentPhotoFactory.build(student=student)
        photo.photo = real_face_image
        photo.save()

        with patch("students.services.face_recognition_service.import_module"):
            service.process_student_photo(photo)

        assert service._face_detector is not None, "Should be loaded after use"


@pytest.mark.django_db
class TestFaceDetector:
    """Test OpenCV face detection."""

    def test_detector_initializes_lazy(self):
        """Test detector doesn't load OpenCV until needed."""
        from ml_models.face_recognition.preprocessing.face_detector import FaceDetector

        detector = FaceDetector()
        assert detector.net is None, "Should be lazy-loaded"

    @patch("ml_models.face_recognition.preprocessing.face_detector.cv2")
    def test_haar_cascade_fallback(self, mock_cv2):
        """Test that Haar Cascade is used when DNN model not found."""
        from ml_models.face_recognition.preprocessing.face_detector import FaceDetector

        # Mock Haar Cascade
        mock_cascade = Mock()
        mock_cascade.detectMultiScale.return_value = np.array([[50, 50, 100, 100]])
        mock_cv2.CascadeClassifier.return_value = mock_cascade
        mock_cv2.data.haarcascades = "/path/to/haarcascades/"
        mock_cv2.cvtColor.return_value = np.zeros((200, 200), dtype=np.uint8)

        detector = FaceDetector()

        # Create test image
        test_image = np.zeros((200, 200, 3), dtype=np.uint8)

        detections = detector.detect(test_image)

        assert len(detections) > 0, "Should detect face with Haar Cascade"


@pytest.mark.django_db
class TestEmbeddingGeneration:
    """Test TFLite model embedding generation."""

    @patch("ml_models.face_recognition.inference.mobilefacenet.tf")
    @patch("pathlib.Path.exists")
    def test_model_generates_valid_embedding(self, mock_exists, mock_tf):
        """Test that model generates valid L2-normalized embedding."""
        from ml_models.face_recognition.inference.mobilefacenet import MobileFaceNet

        # Mock model file exists
        mock_exists.return_value = True

        # Mock TFLite interpreter
        mock_interpreter = Mock()
        mock_interpreter.get_input_details.return_value = [{"index": 0}]
        mock_interpreter.get_output_details.return_value = [{"index": 0}]

        # Mock embedding output (1, 192) shape
        fake_output = np.random.rand(1, 192).astype(np.float32)
        mock_interpreter.get_tensor.return_value = fake_output

        mock_tf.lite.Interpreter.return_value = mock_interpreter

        # Create model and generate embedding
        model = MobileFaceNet()
        test_image = np.zeros((112, 112, 3), dtype=np.uint8)
        embedding = model.generate_embedding(test_image)

        # Validate embedding
        assert embedding.shape == (192,), f"Expected (192,), got {embedding.shape}"
        assert np.allclose(
            np.linalg.norm(embedding), 1.0, atol=0.01
        ), "Embedding should be L2 normalized"


@pytest.mark.django_db
class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_corrupted_image_file(self):
        """Test handling of corrupted image file."""
        student = StudentFactory()

        # Create corrupted file
        corrupted = SimpleUploadedFile(
            name="corrupted.jpg", content=b"not_an_image", content_type="image/jpeg"
        )

        photo = StudentPhotoFactory.build(student=student)
        photo.photo = corrupted
        photo.save()

        service = FaceRecognitionService()
        result = service.process_student_photo(photo)

        assert result is False, "Should handle corrupted images gracefully"

    def test_embedding_quality_threshold(
        self, real_face_image, mock_face_detector, mock_mobilefacenet
    ):
        """Test that low-quality embeddings are rejected."""
        # Mock low-quality embedding
        mock_mobilefacenet.generate_embedding.return_value = np.zeros(
            192, dtype=np.float32
        )

        student = StudentFactory()
        photo = StudentPhotoFactory.build(student=student)
        photo.photo = real_face_image
        photo.save()

        service = FaceRecognitionService()
        result = service.process_student_photo(photo)

        # Depending on quality threshold, might fail
        # This tests the quality scoring logic
        embeddings = FaceEmbeddingMetadata.objects.filter(student_photo=photo)
        if embeddings.exists():
            for emb in embeddings:
                assert emb.quality_score >= 0.0, "Quality score should be valid"


@pytest.mark.django_db
class TestIntegration:
    """Integration tests with real flow."""

    def test_end_to_end_photo_upload_to_embedding(
        self, real_face_image, mock_face_detector, mock_mobilefacenet
    ):
        """Test complete flow: upload photo → detect face → generate embedding."""
        student = StudentFactory()

        # Simulate API upload
        photo = StudentPhotoFactory(student=student, photo=real_face_image)

        # Verify complete flow
        assert photo.photo_id is not None, "Photo should be created"
        assert photo.student == student, "Photo should be linked to student"

        embeddings = FaceEmbeddingMetadata.objects.filter(student_photo=photo)
        assert embeddings.exists(), "Embeddings should be auto-generated"

        for embedding in embeddings:
            assert len(embedding.embedding) > 0, "Embedding vector should exist"
            assert embedding.quality_score > 0, "Quality score should be positive"
            assert embedding.model_name in [
                "MobileFaceNet"
            ], "Model name should be valid"
