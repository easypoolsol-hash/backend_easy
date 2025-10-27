from django.contrib.auth.models import Group
from rest_framework import serializers

from .models import APIKey, AuditLog, User


class GroupSerializer(serializers.ModelSerializer):
    """
    Serializer for Django Groups (Roles).
    Read-only following IAM principle.
    """

    permissions_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ["id", "name", "permissions_count"]
        read_only_fields = ["id", "name", "permissions_count"]

    def get_permissions_count(self, obj):
        return obj.permissions.count()


class UserSerializer(serializers.ModelSerializer):
    groups: list[str] = serializers.StringRelatedField(many=True, read_only=True)
    group_names = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "user_id",
            "username",
            "email",
            "groups",
            "group_names",
            "is_active",
            "last_login",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user_id", "last_login", "created_at", "updated_at"]
        extra_kwargs = {"password": {"write_only": True}}

    def get_group_names(self, obj):
        """Return list of group names for convenience"""
        return list(obj.groups.values_list("name", flat=True))


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    password_confirm = serializers.CharField(write_only=True, required=True)
    group_names = serializers.ListField(child=serializers.CharField(), write_only=True, required=False, allow_empty=True)

    class Meta:
        model = User
        fields = ["username", "email", "password", "password_confirm", "group_names"]

    def validate(self, data):
        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError("Passwords do not match")
        return data

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        group_names = validated_data.pop("group_names", [])

        user = User.objects.create_user(**validated_data)

        # Assign groups if provided
        if group_names:
            groups = Group.objects.filter(name__in=group_names)
            user.groups.set(groups)

        return user


class APIKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = APIKey
        fields = [
            "key_id",
            "kiosk_id",
            "name",
            "permissions",
            "is_active",
            "expires_at",
            "last_used",
            "created_at",
        ]
        read_only_fields = ["key_id", "key_hash", "last_used", "created_at"]


class APIKeyCreateSerializer(serializers.ModelSerializer):
    raw_key = serializers.CharField(read_only=True)

    class Meta:
        model = APIKey
        fields = ["kiosk_id", "name", "permissions", "expires_at", "raw_key"]

    def create(self, validated_data):
        import secrets

        from django.contrib.auth.hashers import make_password

        # Generate a secure API key
        raw_key = secrets.token_urlsafe(32)
        validated_data["key_hash"] = make_password(raw_key)

        api_key = super().create(validated_data)
        # Add the raw key to the response (only shown once)
        api_key.raw_key = raw_key
        return api_key


class AuditLogSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "log_id",
            "user",
            "user_username",
            "user_email",
            "action",
            "resource_type",
            "resource_id",
            "changes",
            "ip_address",
            "user_agent",
            "timestamp",
        ]
        read_only_fields = ["log_id", "timestamp"]
