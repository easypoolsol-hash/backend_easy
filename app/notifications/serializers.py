from rest_framework import serializers

from notifications.models import FCMToken, Notification, NotificationPreference


class FCMTokenSerializer(serializers.ModelSerializer):
    """
    Serializer for registering/managing FCM tokens.

    Google Pattern: Infrastructure operation - works for any authenticated user.
    Parent record auto-created by signal on user creation (pending status).
    """

    class Meta:
        model = FCMToken
        fields = ["token", "platform"]

    def create(self, validated_data):
        user = self.context["request"].user
        token = validated_data["token"]

        # Get parent profile (auto-created by signal)
        if not hasattr(user, "parent_profile") or not user.parent_profile:
            raise serializers.ValidationError("Parent profile not found. Please contact support.")

        parent = user.parent_profile

        # Google Pattern: update_or_create handles duplicate tokens gracefully
        # Same token = update timestamp, Different token = new device
        fcm_token, _created = FCMToken.objects.update_or_create(
            token=token,
            defaults={
                "parent": parent,
                "platform": validated_data.get("platform", "android"),
                "is_active": True,
            },
        )
        return fcm_token


class FCMTokenDeleteSerializer(serializers.Serializer):
    """Serializer for deleting FCM token on logout."""

    token = serializers.CharField(max_length=255)


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for notification preferences."""

    class Meta:
        model = NotificationPreference
        fields = [
            "boarding",
            "deboarding",
            "eta",
            "pickup_reminder",
            "drop_reminder",
            "announcements",
            "quiet_hours_enabled",
            "quiet_hours_start",
            "quiet_hours_end",
        ]


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for notification list/detail."""

    student_name = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "notification_id",
            "notification_type",
            "title",
            "body",
            "data",
            "status",
            "student_name",
            "created_at",
            "read_at",
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        if obj.student:
            return obj.student.encrypted_name
        return None


class NotificationProcessSerializer(serializers.Serializer):
    """Serializer for Cloud Tasks callback."""

    notification_id = serializers.CharField(max_length=26)
