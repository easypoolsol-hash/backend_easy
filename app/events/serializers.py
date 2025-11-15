import base64

from rest_framework import serializers

from .models import AttendanceRecord, BoardingEvent


class BoardingEventSerializer(serializers.ModelSerializer):
    """Serializer for boarding events"""

    class Meta:
        model = BoardingEvent
        fields = [
            "event_id",
            "student",
            "kiosk_id",
            "confidence_score",
            "timestamp",
            "latitude",
            "longitude",
            "bus_route",
            "face_image_url",
            "model_version",
            "metadata",
            "created_at",
        ]
        read_only_fields = ["event_id", "created_at"]

    def validate_confidence_score(self, value):
        """Validate confidence score is between 0 and 1"""
        if not (0.0 <= value <= 1.0):
            raise serializers.ValidationError("Confidence score must be between 0.0 and 1.0")
        return value


class BoardingEventCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating boarding events (kiosk-facing)"""

    # List of base64-encoded confirmation face images (flexible: 1-3 faces)
    confirmation_faces_base64 = serializers.ListField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        write_only=True,
        allow_empty=True,
        max_length=3,  # Max 3 faces to match database storage
        help_text="Array of base64-encoded confirmation faces (112x112 JPEG). Send up to 3 consecutive frames.",
    )

    class Meta:
        model = BoardingEvent
        fields = [
            "event_id",
            "student",
            "kiosk_id",
            "confidence_score",
            "timestamp",
            "gps_coords",
            "bus_route",
            "face_image_url",
            "model_version",
            "metadata",
            "confirmation_faces_base64",
        ]
        read_only_fields = ["event_id"]

    def create(self, validated_data):
        """Create boarding event with confirmation faces stored in Google Cloud Storage.

        This method:
        1. Creates the BoardingEvent with auto-generated ULID
        2. Uploads confirmation face images to GCS
        3. Stores GCS paths in the database (not binary data)

        Args:
            validated_data: Validated data from the serializer.

        Returns:
            Created BoardingEvent instance with GCS paths populated.

        Raises:
            serializers.ValidationError: If base64 decoding or GCS upload fails.
        """
        # Ensure metadata has default event_type if not provided
        if "metadata" not in validated_data or not validated_data["metadata"]:
            validated_data["metadata"] = {}

        # Set default event_type to 'boarding' if not specified
        if "event_type" not in validated_data["metadata"]:
            validated_data["metadata"]["event_type"] = "boarding"

        # Extract confirmation faces (don't add to BoardingEvent yet)
        confirmation_faces_base64 = validated_data.pop("confirmation_faces_base64", [])

        # Create the boarding event first (generates ULID)
        boarding_event = BoardingEvent.objects.create(**validated_data)

        # Upload confirmation faces to Google Cloud Storage
        if confirmation_faces_base64:
            from .services.storage_service import BoardingEventStorageService

            try:
                storage_service = BoardingEventStorageService()

                # Upload each face and store GCS path
                for idx, face_base64 in enumerate(confirmation_faces_base64[:3], start=1):
                    try:
                        # Decode base64 image
                        image_bytes = base64.b64decode(face_base64)

                        # Upload to GCS
                        gcs_path = storage_service.upload_confirmation_face(
                            event_id=boarding_event.event_id,
                            face_number=idx,
                            image_bytes=image_bytes,
                            content_type="image/jpeg",
                        )

                        # Store GCS path in model
                        setattr(boarding_event, f"confirmation_face_{idx}_gcs", gcs_path)

                    except Exception as e:
                        # Clean up: Delete the boarding event and any uploaded faces
                        storage_service.delete_confirmation_faces(boarding_event.event_id)
                        boarding_event.delete()
                        raise serializers.ValidationError({"confirmation_faces_base64": f"Failed to process face {idx}: {e!s}"}) from None

                # Save GCS paths to database
                boarding_event.save(
                    update_fields=[
                        "confirmation_face_1_gcs",
                        "confirmation_face_2_gcs",
                        "confirmation_face_3_gcs",
                    ]
                )

            except Exception as e:
                # Clean up: Delete the boarding event
                boarding_event.delete()
                raise serializers.ValidationError({"confirmation_faces_base64": f"GCS upload failed: {e!s}"}) from None

        return boarding_event


class AttendanceRecordSerializer(serializers.ModelSerializer):
    """Serializer for attendance records"""

    student_name = serializers.CharField(source="student.name", read_only=True)
    student_grade = serializers.CharField(source="student.grade", read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            "record_id",
            "student",
            "student_name",
            "student_grade",
            "date",
            "morning_boarded",
            "morning_time",
            "afternoon_boarded",
            "afternoon_time",
            "status",
            "created_at",
        ]
        read_only_fields = ["record_id", "status", "created_at"]


class AttendanceSummarySerializer(serializers.Serializer):
    """Serializer for attendance summary statistics"""

    date = serializers.DateField()
    total_students = serializers.IntegerField()
    present_count = serializers.IntegerField()
    absent_count = serializers.IntegerField()
    partial_count = serializers.IntegerField()
    attendance_rate = serializers.FloatField()
