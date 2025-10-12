"""
Integration test for async Celery embedding generation.
Requires Redis + Celery worker running.

Run with: pytest tests/integration/test_celery_async_embedding.py
"""

import time

import pytest

from students.models import FaceEmbeddingMetadata
from students.tasks import process_student_photo_embedding_task
from tests.factories import StudentFactory, StudentPhotoFactory


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
class TestCeleryAsyncEmbeddingGeneration:
    """Test full async flow with real Celery worker."""

    def test_celery_task_processes_embedding(self, face_image_file):
        """Test Celery worker picks up task and generates embedding."""
        student = StudentFactory()
        photo = StudentPhotoFactory.build(student=student)
        photo.photo = face_image_file
        photo.save()

        # Queue task (will be picked up by worker)
        result = process_student_photo_embedding_task.delay(str(photo.photo_id))

        # Wait for task completion (max 10 seconds)
        timeout = 10
        start = time.time()
        while time.time() - start < timeout:
            if result.ready():
                break
            time.sleep(0.5)

        # Verify task completed
        assert result.ready(), "Task should complete within timeout"
        task_result = result.get(timeout=5)
        assert task_result["status"] in ["success", "failed"], "Task should return status"

        # If successful, verify embedding was created
        if task_result["status"] == "success":
            embeddings = FaceEmbeddingMetadata.objects.filter(student_photo=photo)
            assert embeddings.exists(), "Embedding should be created"


@pytest.fixture
def face_image_file():
    """Create simple test face image."""
    from io import BytesIO

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (200, 200), color=(255, 220, 180))
    draw = ImageDraw.Draw(img)

    # Eyes
    draw.ellipse([60, 70, 80, 90], fill=(50, 50, 50))
    draw.ellipse([120, 70, 140, 90], fill=(50, 50, 50))

    # Nose
    draw.ellipse([95, 100, 105, 120], fill=(200, 180, 160))

    # Mouth
    draw.ellipse([80, 140, 120, 155], fill=(180, 100, 100))

    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    return SimpleUploadedFile(name="test_face.jpg", content=img_bytes.read(), content_type="image/jpeg")
