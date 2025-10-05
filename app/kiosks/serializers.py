import hashlib

from rest_framework import serializers

from .models import DeviceLog, Kiosk


class KioskSerializer(serializers.ModelSerializer):
    """Serializer for kiosks"""

    bus = serializers.CharField(source="bus.bus_id", read_only=True)
    bus_license_plate = serializers.CharField(
        source="bus.license_plate", read_only=True
    )
    status_display = serializers.ReadOnlyField()
    is_online = serializers.ReadOnlyField()
    battery_level = serializers.FloatField(required=False)

    class Meta:
        model = Kiosk
        fields = [
            "kiosk_id",
            "bus",
            "bus_license_plate",
            "firmware_version",
            "last_heartbeat",
            "is_active",
            "battery_level",
            "storage_used_mb",
            "status_display",
            "is_online",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["kiosk_id", "created_at", "updated_at", "api_key_hash"]

    def validate_battery_level(self, value):
        """Validate battery level is between 0 and 100"""
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError("Battery level must be between 0 and 100")
        return value


class KioskHeartbeatSerializer(serializers.Serializer):
    """
    Serializer for kiosk heartbeat data (Fortune 500 pattern)

    kiosk_id is optional - kiosk is authenticated via JWT.
    If provided, it's verified to match the authenticated kiosk (security check).
    """

    kiosk_id = serializers.CharField(max_length=100, required=False)
    firmware_version = serializers.CharField(max_length=50, required=False)
    battery_level = serializers.IntegerField(required=False, min_value=0, max_value=100)
    storage_used_mb = serializers.IntegerField(required=False, min_value=0)

    def validate_kiosk_id(self, value):
        """
        Optional security check: If kiosk_id provided, verify it matches authenticated kiosk.
        Prevents token reuse attacks.
        """
        # Get authenticated kiosk from context (set by view from request.user)
        authenticated_kiosk = self.context.get('kiosk')

        if authenticated_kiosk and value and value != authenticated_kiosk.kiosk_id:
            # Security violation: JWT token doesn't match kiosk_id in request
            raise serializers.ValidationError("kiosk_id mismatch with authentication")

        return value


class DeviceLogSerializer(serializers.ModelSerializer):
    """Serializer for device logs"""

    kiosk_id = serializers.CharField(source="kiosk.kiosk_id", read_only=True)

    class Meta:
        model = DeviceLog
        fields = [
            "log_id",
            "kiosk",
            "kiosk_id",
            "log_level",
            "message",
            "metadata",
            "timestamp",
        ]
        read_only_fields = ["log_id", "timestamp"]


class KioskStatusSerializer(serializers.Serializer):
    """Serializer for kiosk status summary"""

    total_kiosks = serializers.IntegerField()
    active_kiosks = serializers.IntegerField()
    online_kiosks = serializers.IntegerField()
    offline_kiosks = serializers.IntegerField()
    kiosks = KioskSerializer(many=True)


class KioskAuthSerializer(serializers.Serializer):
    """
    Serializer for kiosk authentication

    Fortune 500 Pattern:
    - Validate input format
    - Hash API key before database lookup
    - Return structured error messages
    - No sensitive data in responses
    """

    kiosk_id = serializers.CharField(
        max_length=100,
        required=True,
        error_messages={
            'required': 'Kiosk ID is required',
            'blank': 'Kiosk ID cannot be blank',
            'max_length': 'Kiosk ID too long (max 100 characters)'
        }
    )
    api_key = serializers.CharField(
        max_length=255,
        required=True,
        write_only=True,  # Never return API key in response
        error_messages={
            'required': 'API key is required',
            'blank': 'API key cannot be blank',
        }
    )

    def validate(self, attrs):
        """
        Validate kiosk credentials (Fortune 500 security pattern)

        Steps:
        1. Hash the provided API key
        2. Lookup kiosk by ID and hashed key
        3. Verify kiosk is active
        4. Store kiosk object in context for view
        """
        kiosk_id = attrs.get('kiosk_id')
        api_key = attrs.get('api_key')

        # Hash API key (same method as during kiosk creation)
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Attempt to find kiosk with matching credentials
        try:
            kiosk = Kiosk.objects.select_related('bus').get(
                kiosk_id=kiosk_id,
                api_key_hash=api_key_hash
            )
        except Kiosk.DoesNotExist as e:
            # Security: Use generic error message (don't reveal if kiosk_id exists)
            raise serializers.ValidationError(
                {'detail': 'Invalid kiosk credentials'}
            ) from e

        # Verify kiosk is active
        if not kiosk.is_active:
            raise serializers.ValidationError(
                {'detail': 'Kiosk is inactive. Contact administrator.'}
            )

        # Store kiosk in context for view to use
        self.context['kiosk'] = kiosk

        return attrs


class KioskAuthResponseSerializer(serializers.Serializer):
    """Serializer for authentication response"""

    access = serializers.CharField(help_text="JWT access token (expires in 24h)")
    refresh = serializers.CharField(help_text="JWT refresh token (expires in 7 days)")
    kiosk_id = serializers.CharField(help_text="Authenticated kiosk ID")
    bus_id = serializers.UUIDField(help_text="Assigned bus ID", allow_null=True)
    expires_in = serializers.IntegerField(help_text="Token expiry in seconds")
