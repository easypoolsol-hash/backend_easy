"""Google Cloud Storage service for boarding event confirmation faces.

This module provides utilities for uploading confirmation face images to Google Cloud Storage
and generating signed URLs for secure private access.

Typical usage example:
    storage_service = BoardingEventStorageService()
    gcs_path = storage_service.upload_confirmation_face(
        event_id="01HQXYZ123",
        face_number=1,
        image_bytes=image_data
    )
    signed_url = storage_service.get_signed_url(gcs_path)
"""

from datetime import timedelta
import os

from google.cloud import storage

from ..models import MAX_CONFIRMATION_FACES


class BoardingEventStorageService:
    """Service for managing boarding event confirmation face images in Google Cloud Storage.

    This service handles:
    - Uploading confirmation face images to GCS
    - Generating signed URLs for secure access
    - Managing bucket connections and credentials

    Attributes:
        bucket_name: Name of the GCS bucket for backend storage.
        client: Google Cloud Storage client instance.
        bucket: GCS bucket instance.
    """

    def __init__(self):
        """Initializes the storage service with GCS bucket connection.

        Raises:
            ValueError: If GCS_BUCKET_NAME environment variable is not set.
            google.api_core.exceptions.GoogleAPIError: If bucket access fails.
        """
        self.bucket_name = os.getenv("GCS_BUCKET_NAME")
        if not self.bucket_name:
            raise ValueError("GCS_BUCKET_NAME environment variable not set. Configure it in Terraform backend-service configuration.")

        # Initialize GCS client
        # On Cloud Run, this automatically uses the service account attached to the instance
        # For local development, set GOOGLE_APPLICATION_CREDENTIALS environment variable
        self.client = storage.Client()
        self.bucket = self.client.bucket(self.bucket_name)

    def upload_confirmation_face(
        self,
        event_id: str,
        face_number: int,
        image_bytes: bytes,
        content_type: str = "image/jpeg",
    ) -> str:
        """Uploads a confirmation face image to Google Cloud Storage.

        Args:
            event_id: The ULID of the boarding event.
            face_number: The face number (1, 2, or 3).
            image_bytes: The image data as bytes.
            content_type: MIME type of the image (default: image/jpeg).

        Returns:
            The GCS path of the uploaded image (e.g., "boarding_events/01HQXYZ123/face_1.jpg").

        Raises:
            ValueError: If face_number is out of range (1 to MAX_CONFIRMATION_FACES).
            google.api_core.exceptions.GoogleAPIError: If upload fails.
        """
        valid_range = list(range(1, MAX_CONFIRMATION_FACES + 1))
        if face_number not in valid_range:
            raise ValueError(f"face_number must be in {valid_range}, got {face_number}")

        # Google Cloud Storage path format: boarding_events/{event_id}/face_{number}.jpg
        gcs_path = f"boarding_events/{event_id}/face_{face_number}.jpg"

        # Create blob and upload
        blob = self.bucket.blob(gcs_path)
        blob.upload_from_string(
            image_bytes,
            content_type=content_type,
        )

        return gcs_path

    def get_signed_url(
        self,
        gcs_path: str,
        expiration_minutes: int = 60,
    ) -> str:
        """Generates a signed URL for temporary secure access to a private GCS object.

        Args:
            gcs_path: The GCS path of the object (e.g., "boarding_events/01HQXYZ123/face_1.jpg").
            expiration_minutes: URL expiration time in minutes (default: 60).

        Returns:
            A signed URL that provides temporary access to the object.

        Raises:
            google.api_core.exceptions.GoogleAPIError: If signed URL generation fails.

        Note:
            On Cloud Run, this uses the IAM signBlob API (no service account key needed).
            Requires: IAM Service Account Credentials API enabled + Token Creator role.
        """
        from google import auth
        from google.auth.transport import requests

        blob = self.bucket.blob(gcs_path)

        # Get default credentials (works on Cloud Run, GCE, local with GOOGLE_APPLICATION_CREDENTIALS)
        credentials, project_id = auth.default()

        # Refresh credentials to obtain access token (required for signing)
        auth_request = requests.Request()
        credentials.refresh(auth_request)

        # Generate signed URL using IAM signBlob API
        # Requires both service_account_email and access_token for Cloud Run
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET",
            service_account_email=credentials.service_account_email,
            access_token=credentials.token,
        )

        return signed_url

    def download_image(self, gcs_path: str) -> bytes | None:
        """Downloads an image from Google Cloud Storage.

        Args:
            gcs_path: The GCS path of the object to download.

        Returns:
            The image data as bytes, or None if the object doesn't exist.

        Raises:
            google.api_core.exceptions.GoogleAPIError: If download fails.
        """
        blob = self.bucket.blob(gcs_path)

        if not blob.exists():
            return None

        return blob.download_as_bytes()

    def delete_confirmation_faces(self, event_id: str) -> None:
        """Deletes all confirmation face images for a boarding event.

        Args:
            event_id: The ULID of the boarding event.

        Raises:
            google.api_core.exceptions.GoogleAPIError: If deletion fails.

        Note:
            This is used when a boarding event is deleted (super admin only).
            Deletes all confirmation face images (uses MAX_CONFIRMATION_FACES config).
        """
        for face_number in range(1, MAX_CONFIRMATION_FACES + 1):
            gcs_path = f"boarding_events/{event_id}/face_{face_number}.jpg"
            blob = self.bucket.blob(gcs_path)

            # Delete only if exists (no error if not found)
            if blob.exists():
                blob.delete()
