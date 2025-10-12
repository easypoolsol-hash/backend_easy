"""
Quick test script to debug embedding generation issue.
Run: python app/manage.py shell < test_embedding_generation.py
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bus_kiosk_backend.settings')
django.setup()

from students.models import StudentPhoto, FaceEmbeddingMetadata
from students.services.face_recognition_service import FaceRecognitionService
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

print("=" * 60)
print("EMBEDDING GENERATION DEBUG TEST")
print("=" * 60)

# Get the photo you just uploaded
photo_id = "c5cd88ef-7d13-44e4-8868-9f12fc5f9b45"

try:
    photo = StudentPhoto.objects.get(photo_id=photo_id)
    print(f"\n✓ Found photo: {photo.photo_id}")
    print(f"  Student: {photo.student}")
    print(f"  Photo file: {photo.photo.name if photo.photo else 'None'}")
    print(f"  Captured at: {photo.captured_at}")

    # Check existing embeddings
    existing_embeddings = FaceEmbeddingMetadata.objects.filter(student_photo=photo)
    print(f"\n  Existing embeddings: {existing_embeddings.count()}")

    if existing_embeddings.count() == 0:
        print("\n⚠ No embeddings found. Running face recognition service...")

        # Try to process manually
        service = FaceRecognitionService()
        print(f"\n  Enabled models: {list(service.enabled_models.keys())}")

        # Process the photo
        print("\n  Processing photo...")
        result = service.process_student_photo(photo)

        if result:
            print("\n✓ SUCCESS: Embeddings generated!")

            # Check embeddings again
            new_embeddings = FaceEmbeddingMetadata.objects.filter(student_photo=photo)
            print(f"  New embeddings count: {new_embeddings.count()}")

            for emb in new_embeddings:
                print(f"    - Model: {emb.model_name}, Quality: {emb.quality_score:.3f}, Dims: {len(emb.embedding)}")
        else:
            print("\n✗ FAILED: Could not generate embeddings")
            print("\n  Possible reasons:")
            print("    1. No face detected in image")
            print("    2. Face too small or poor quality")
            print("    3. Multiple faces detected")
            print("    4. Image file corrupted")
    else:
        print("\n✓ Embeddings already exist:")
        for emb in existing_embeddings:
            print(f"    - Model: {emb.model_name}, Quality: {emb.quality_score:.3f}")

except StudentPhoto.DoesNotExist:
    print(f"\n✗ ERROR: Photo {photo_id} not found in database")
except Exception as e:
    print(f"\n✗ ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
