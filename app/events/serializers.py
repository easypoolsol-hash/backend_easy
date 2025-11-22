import base64

from rest_framework import serializers

from .models import MAX_CONFIRMATION_FACES, AttendanceRecord, BoardingEvent


class BoardingEventSerializer(serializers.ModelSerializer):
    """Serializer for boarding events"""

    # Dynamic list of confirmation face URLs (flexible - works with any number of photos)
    confirmation_face_urls = serializers.SerializerMethodField()
    # Flag to identify unknown/unidentified faces
    is_unknown_face = serializers.SerializerMethodField()

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
            "confirmation_face_urls",
            "is_unknown_face",
        ]
        read_only_fields = ["event_id", "created_at"]

    def get_confirmation_face_urls(self, obj):
        """Get all available confirmation face URLs dynamically.

        Returns list of signed URLs for all confirmation faces that exist.
        Easily adjustable via MAX_CONFIRMATION_FACES constant.

        Performance optimization:
        - If `include_photos=false` in query params, returns empty list
        - This allows page load without waiting for signed URL generation
        - Use separate `/events/{id}/photos/` endpoint for lazy loading
        """
        # Check if request context has include_photos=false
        request = self.context.get("request")
        if request and request.query_params.get("include_photos", "true").lower() == "false":
            return []

        urls = []
        # Dynamically get all confirmation face URLs (uses MAX_CONFIRMATION_FACES config)
        for i in range(1, MAX_CONFIRMATION_FACES + 1):
            url = getattr(obj, f"confirmation_face_{i}_url", None)
            if url:
                urls.append(url)
        return urls

    def get_is_unknown_face(self, obj):
        """Check if this is an unknown/unidentified face event."""
        return obj.student is None

    def validate_confidence_score(self, value):
        """Validate confidence score is between 0 and 1"""
        if not (0.0 <= value <= 1.0):
            raise serializers.ValidationError("Confidence score must be between 0.0 and 1.0")
        return value


class BoardingEventCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating boarding events (kiosk-facing)"""

    # List of base64-encoded confirmation face images (flexible: adjustable via MAX_CONFIRMATION_FACES)
    confirmation_faces_base64 = serializers.ListField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        write_only=True,
        allow_empty=True,
        max_length=MAX_CONFIRMATION_FACES,  # Flexible: uses MAX_CONFIRMATION_FACES config
        help_text=f"Array of base64-encoded confirmation faces (112x112 JPEG). Send up to {MAX_CONFIRMATION_FACES} consecutive frames.",
    )
    # GPS coordinates as [latitude, longitude] list (write-only, converted to lat/lon fields)
    gps_coords = serializers.ListField(
        child=serializers.FloatField(),
        required=False,
        write_only=True,
        allow_null=True,
        min_length=2,
        max_length=2,
        help_text="GPS coordinates as [latitude, longitude]. Optional - boarding events can be created without location.",
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

    def validate_gps_coords(self, value):
        """Validate GPS coordinates are within valid ranges."""
        if value is None:
            return value

        if len(value) != 2:
            raise serializers.ValidationError("GPS coordinates must be [latitude, longitude]")

        latitude, longitude = value

        # Validate latitude range (-90 to 90)
        if not (-90.0 <= latitude <= 90.0):
            raise serializers.ValidationError(f"Latitude must be between -90 and 90, got {latitude}")

        # Validate longitude range (-180 to 180)
        if not (-180.0 <= longitude <= 180.0):
            raise serializers.ValidationError(f"Longitude must be between -180 and 180, got {longitude}")

        return value

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
        # Handle unknown face events: Convert "UNKNOWN" student ID to None
        # Kiosk sends "UNKNOWN" for unidentified faces due to interface constraints
        student = validated_data.get("student")
        if student is not None and hasattr(student, "school_student_id") and student.school_student_id == "UNKNOWN":
            validated_data["student"] = None
        elif isinstance(student, str) and student == "UNKNOWN":
            validated_data["student"] = None

        # Ensure metadata has default event_type if not provided
        if "metadata" not in validated_data or not validated_data["metadata"]:
            validated_data["metadata"] = {}

        # Set default event_type to 'boarding' if not specified
        if "event_type" not in validated_data["metadata"]:
            validated_data["metadata"]["event_type"] = "boarding"

        # Extract confirmation faces (don't add to BoardingEvent yet)
        confirmation_faces_base64 = validated_data.pop("confirmation_faces_base64", [])

        # Extract and convert GPS coordinates to latitude/longitude fields
        gps_coords = validated_data.pop("gps_coords", None)
        if gps_coords:
            validated_data["latitude"] = gps_coords[0]
            validated_data["longitude"] = gps_coords[1]

        # Create the boarding event first (generates ULID)
        boarding_event = BoardingEvent.objects.create(**validated_data)

        # Upload confirmation faces to Google Cloud Storage
        if confirmation_faces_base64:
            from .services.storage_service import BoardingEventStorageService

            try:
                storage_service = BoardingEventStorageService()

                # Upload each face and store GCS path (uses MAX_CONFIRMATION_FACES config)
                for idx, face_base64 in enumerate(confirmation_faces_base64[:MAX_CONFIRMATION_FACES], start=1):
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

                # Save GCS paths to database (dynamically build field list)
                update_fields = [f"confirmation_face_{i}_gcs" for i in range(1, MAX_CONFIRMATION_FACES + 1)]
                boarding_event.save(update_fields=update_fields)

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
