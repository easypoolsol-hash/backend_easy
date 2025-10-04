from typing import Any

from django.utils import timezone
import factory
from factory.django import DjangoModelFactory

from buses.models import Bus

from .models import DeviceLog, Kiosk


class BusFactory(DjangoModelFactory):
    """Factory for Bus model"""

    class Meta:
        model = Bus

    license_plate = factory.Sequence(lambda n: f"BUS-{n:03d}")
    capacity = 50
    model = factory.Sequence(lambda n: f"Model-{n}")
    status = 'active'


class KioskFactory(DjangoModelFactory):
    """Factory for Kiosk model"""

    class Meta:
        model = Kiosk

    kiosk_id = factory.Sequence(lambda n: f"KIOSK-{n:03d}")
    bus: Any = factory.SubFactory(BusFactory)
    api_key_hash = factory.Sequence(lambda n: f"hash_{n}")
    firmware_version = "1.0.0"
    battery_level = 85.5
    storage_used_mb = 1024
    is_active = True
    last_heartbeat = factory.LazyFunction(timezone.now)


class DeviceLogFactory(DjangoModelFactory):
    """Factory for DeviceLog model"""

    class Meta:
        model = DeviceLog

    kiosk: Any = factory.SubFactory(KioskFactory)
    log_level = "INFO"
    message: Any = factory.Faker('sentence')
    metadata = factory.LazyFunction(lambda: {'test': True})
