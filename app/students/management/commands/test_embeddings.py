"""
Django management command to test face embedding generation.
Usage: python manage.py test_embeddings <photo_id>
"""

import logging
from typing import Any

from django.core.management.base import BaseCommand

from students.models import FaceEmbeddingMetadata, StudentPhoto
from students.services.face_recognition_service import FaceRecognitionService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Test face embedding generation for a specific photo"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("photo_id", type=str, help="Photo ID (UUID) to process")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force reprocess even if embeddings exist",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        photo_id = options["photo_id"]
        force = options.get("force", False)

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("FACE EMBEDDING GENERATION TEST"))
        self.stdout.write("=" * 70)

        try:
            # Get the photo
            photo = StudentPhoto.objects.get(photo_id=photo_id)
            self.stdout.write(f"\nFound photo: {photo.photo_id}")
            self.stdout.write(f"  Student: {photo.student}")
            photo_file_name = photo.photo.name if photo.photo else "None"
            file_exists = photo.photo.storage.exists(photo.photo.name) if photo.photo else False
            self.stdout.write(f"  Photo file: {photo_file_name}")
            self.stdout.write(f"  File exists: {file_exists}")

            # Check existing embeddings
            existing_embeddings = FaceEmbeddingMetadata.objects.filter(student_photo=photo)
            self.stdout.write(f"\nExisting embeddings: {existing_embeddings.count()}")

            if existing_embeddings.exists() and not force:
                self.stdout.write(self.style.WARNING("\nEmbeddings already exist. Use --force to reprocess."))
                for emb in existing_embeddings:
                    self.stdout.write(f"  - {emb.model_name}: quality={emb.quality_score:.3f}, dims={len(emb.embedding)}")
                return

            # Initialize service
            self.stdout.write("\nInitializing face recognition service...")
            service = FaceRecognitionService()
            enabled = list(service.enabled_models.keys())
            self.stdout.write(f"  Enabled models: {enabled}")

            # Process photo
            self.stdout.write("\nProcessing photo...")
            self.stdout.write(self.style.WARNING("  (This will take 10-30 seconds...)"))

            # Enable detailed logging
            logging.basicConfig(level=logging.DEBUG)

            result = service.process_student_photo(photo)

            if result:
                self.stdout.write(self.style.SUCCESS("\n SUCCESS: Embeddings generated!"))

                # Show results
                new_embeddings = FaceEmbeddingMetadata.objects.filter(student_photo=photo)
                self.stdout.write(f"\nGenerated {new_embeddings.count()} embeddings:")

                for emb in new_embeddings:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  - Model: {emb.model_name}\n"
                            f"    Quality: {emb.quality_score:.3f}\n"
                            f"    Dimensions: {len(emb.embedding)}\n"
                            f"    Captured: {emb.captured_at}"
                        )
                    )
            else:
                self.stdout.write(self.style.ERROR("\n FAILED: Could not generate embeddings"))
                self.stdout.write("\nPossible reasons:")
                self.stdout.write("  1. No face detected in image")
                self.stdout.write("  2. Face too small or poor quality")
                self.stdout.write("  3. Multiple faces detected (limit is 1)")
                self.stdout.write("  4. Image file corrupted or unreadable")
                self.stdout.write("  5. ML model loading failed")
                self.stdout.write("\nCheck logs above for detailed error messages.")

        except StudentPhoto.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"\n ERROR: Photo {photo_id} not found"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n ERROR: {type(e).__name__}: {e}"))
            import traceback

            self.stdout.write(traceback.format_exc())

        self.stdout.write("\n" + "=" * 70)
