from rest_framework import serializers

from .models import DeviceLog, Kiosk


class KioskSerializer(serializers.ModelSerializer):
    """Serializer for kiosks"""

    bus = serializers.CharField(source='bus.bus_id', read_only=True)
    bus_license_plate = serializers.CharField(
        source='bus.license_plate', read_only=True
    )
    status_display = serializers.ReadOnlyField()
    is_online = serializers.ReadOnlyField()
    battery_level = serializers.FloatField(required=False)

    class Meta:
        model = Kiosk
        fields = [
            'kiosk_id',
            'bus',
            'bus_license_plate',
            'firmware_version',
            'last_heartbeat',
            'is_active',
            'battery_level',
            'storage_used_mb',
            'status_display',
            'is_online',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['kiosk_id', 'created_at', 'updated_at', 'api_key_hash']

    def validate_battery_level(self, value):
        """Validate battery level is between 0 and 100"""
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError("Battery level must be between 0 and 100")
        return value


class KioskHeartbeatSerializer(serializers.Serializer):
    """Serializer for kiosk heartbeat data"""

    kiosk_id = serializers.CharField(max_length=100)
    firmware_version = serializers.CharField(max_length=50, required=False)
    battery_level = serializers.IntegerField(required=False, min_value=0, max_value=100)
    storage_used_mb = serializers.IntegerField(required=False, min_value=0)

    def validate_kiosk_id(self, value):
        """Validate kiosk exists"""
        try:
            kiosk = Kiosk.objects.get(kiosk_id=value)
            self.context['kiosk'] = kiosk
            return value
        except Kiosk.DoesNotExist as e:
            raise serializers.ValidationError("Kiosk not found") from e


class DeviceLogSerializer(serializers.ModelSerializer):
    """Serializer for device logs"""

    kiosk_id = serializers.CharField(source='kiosk.kiosk_id', read_only=True)

    class Meta:
        model = DeviceLog
        fields = [
            'log_id',
            'kiosk',
            'kiosk_id',
            'log_level',
            'message',
            'metadata',
            'timestamp'
        ]
        read_only_fields = ['log_id', 'timestamp']


class KioskStatusSerializer(serializers.Serializer):
    """Serializer for kiosk status summary"""

    total_kiosks = serializers.IntegerField()
    active_kiosks = serializers.IntegerField()
    online_kiosks = serializers.IntegerField()
    offline_kiosks = serializers.IntegerField()
    kiosks = KioskSerializer(many=True)
