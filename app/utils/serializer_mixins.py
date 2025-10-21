"""
Serializer mixins for common patterns.

Industry Standard: DRY (Don't Repeat Yourself)
===============================================
Following Fortune 500 pattern of extracting common serializer behavior
into reusable mixins.
"""

from rest_framework import serializers

from .timezone_utils import format_datetime_ist, to_ist


class ISTTimezoneMixin:
    """
    Mixin to automatically add IST timezone fields to serializers.

    Usage:
    ------
    class EventSerializer(ISTTimezoneMixin, serializers.ModelSerializer):
        class Meta:
            model = Event
            fields = ['id', 'name', 'timestamp', 'timestamp_ist']
            ist_fields = ['timestamp']  # Specify which datetime fields to convert

    This will automatically add 'timestamp_ist' field with IST conversion.

    Advanced Usage:
    --------------
    class EventSerializer(ISTTimezoneMixin, serializers.ModelSerializer):
        class Meta:
            model = Event
            fields = ['id', 'created_at', 'updated_at', 'created_at_ist', 'updated_at_ist']
            ist_fields = ['created_at', 'updated_at']
            ist_format = '%d-%m-%Y %H:%M:%S'  # Custom format
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Get fields to convert from Meta
        ist_fields = getattr(self.Meta, "ist_fields", [])
        ist_format = getattr(self.Meta, "ist_format", None)

        # Dynamically add IST fields
        for field_name in ist_fields:
            ist_field_name = f"{field_name}_ist"

            # Add the field dynamically
            self.fields[ist_field_name] = serializers.SerializerMethodField()

            # Create the method dynamically
            if ist_format:
                # Custom format
                setattr(
                    self,
                    f"get_{ist_field_name}",
                    lambda obj, fn=field_name, fmt=ist_format: (format_datetime_ist(getattr(obj, fn), fmt) if getattr(obj, fn, None) else None),
                )
            else:
                # ISO format (default)
                setattr(
                    self,
                    f"get_{ist_field_name}",
                    lambda obj, fn=field_name: (to_ist(getattr(obj, fn)).isoformat() if getattr(obj, fn, None) else None),
                )


class TimestampFieldsMixin:
    """
    Mixin that adds created_at and updated_at fields in both UTC and IST.

    Usage:
    ------
    class UserSerializer(TimestampFieldsMixin, serializers.ModelSerializer):
        class Meta:
            model = User
            fields = ['id', 'username', 'created_at', 'created_at_ist',
                     'updated_at', 'updated_at_ist']
    """

    created_at_ist = serializers.SerializerMethodField()
    updated_at_ist = serializers.SerializerMethodField()

    def get_created_at_ist(self, obj):
        """Get created_at in IST."""
        if hasattr(obj, "created_at") and obj.created_at:
            return to_ist(obj.created_at).isoformat()
        return None

    def get_updated_at_ist(self, obj):
        """Get updated_at in IST."""
        if hasattr(obj, "updated_at") and obj.updated_at:
            return to_ist(obj.updated_at).isoformat()
        return None


# Example: How to use in your serializers
"""
# Example 1: Simple usage with mixin
# ==================================

from rest_framework import serializers
from utils.serializer_mixins import ISTTimezoneMixin
from kiosks.models import BusLocation


class BusLocationSerializer(ISTTimezoneMixin, serializers.ModelSerializer):
    class Meta:
        model = BusLocation
        fields = ['id', 'latitude', 'longitude', 'timestamp', 'timestamp_ist']
        ist_fields = ['timestamp']  # Automatically adds 'timestamp_ist'


# API Response will be:
{
    "id": 1,
    "latitude": 22.5726,
    "longitude": 88.3639,
    "timestamp": "2024-01-15T10:00:00Z",  # UTC
    "timestamp_ist": "2024-01-15T15:30:00+05:30"  # IST
}


# Example 2: Multiple fields with custom format
# ==============================================

class BoardingEventSerializer(ISTTimezoneMixin, serializers.ModelSerializer):
    class Meta:
        model = BoardingEvent
        fields = [
            'id',
            'student_name',
            'boarded_at', 'boarded_at_ist',
            'verified_at', 'verified_at_ist'
        ]
        ist_fields = ['boarded_at', 'verified_at']
        ist_format = '%d-%m-%Y %I:%M %p'  # "15-01-2024 03:30 PM"


# API Response will be:
{
    "id": 1,
    "student_name": "John Doe",
    "boarded_at": "2024-01-15T10:00:00Z",
    "boarded_at_ist": "15-01-2024 03:30 PM",
    "verified_at": "2024-01-15T10:00:30Z",
    "verified_at_ist": "15-01-2024 03:30 PM"
}


# Example 3: Manual approach (without mixin)
# ===========================================

from utils.timezone_utils import to_ist


class EventSerializer(serializers.ModelSerializer):
    timestamp_ist = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = ['id', 'name', 'timestamp', 'timestamp_ist']

    def get_timestamp_ist(self, obj):
        '''Return timestamp in IST format.'''
        if obj.timestamp:
            return to_ist(obj.timestamp).isoformat()
        return None


# Example 4: Using TimestampFieldsMixin
# =====================================

from utils.serializer_mixins import TimestampFieldsMixin


class UserSerializer(TimestampFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email',
            'created_at', 'created_at_ist',
            'updated_at', 'updated_at_ist'
        ]

# Automatically gets created_at_ist and updated_at_ist methods
"""
