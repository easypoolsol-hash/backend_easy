from rest_framework import serializers

from notifications.models import FCMToken, Notification, NotificationPreference


class FCMTokenSerializer(serializers.ModelSerializer):
    """Serializer for registering/managing FCM tokens."""

    class Meta:
        model = FCMToken
        fields = ["token", "platform"]

    def create(self, validated_data):
        parent = self.context["request"].user.parent_profile
        token = validated_data["token"]

        # Update or create token
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
