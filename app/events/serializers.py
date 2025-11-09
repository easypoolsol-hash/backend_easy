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
        """
        Create boarding event with auto-generated ULID and default
        metadata. Decode base64 confirmation faces if provided.
        """
        # Ensure metadata has default event_type if not provided
        if "metadata" not in validated_data or not validated_data["metadata"]:
            validated_data["metadata"] = {}

        # Set default event_type to 'boarding' if not specified
        # Later: logic will determine 'pickup' vs 'dropoff'
        # based on time/location
        if "event_type" not in validated_data["metadata"]:
            validated_data["metadata"]["event_type"] = "boarding"

        # Decode confirmation faces from base64 list
        confirmation_faces = validated_data.pop("confirmation_faces_base64", [])

        for idx, face_base64 in enumerate(confirmation_faces[:3], start=1):  # Store up to 3 faces
            try:
                image_data = base64.b64decode(face_base64)
                validated_data[f"confirmation_face_{idx}"] = image_data
            except Exception as e:
                raise serializers.ValidationError({"confirmation_faces_base64": f"Invalid base64 data at index {idx - 1}: {e}"}) from None

        return BoardingEvent.objects.create(**validated_data)


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
