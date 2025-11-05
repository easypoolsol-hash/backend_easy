#!/usr/bin/env python
"""
Pre-register kiosk in Cloud SQL database.
Follows Fortune 500 pattern: admin registers device before deployment.
"""

import os
import sys

import django

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bus_kiosk_backend.settings.production")
django.setup()

from kiosks.models import Kiosk  # noqa: E402

# Pre-register kiosk with firebase_uid
kiosk, created = Kiosk.objects.get_or_create(
    firebase_uid="to2fDdUPP8X6hmkPSEqxExmRlaT2",
    defaults={
        "kiosk_id": "KIOSK001",
        "is_active": False,
    },
)

if created:
    print(f"✅ Created kiosk: {kiosk.kiosk_id} (firebase_uid: {kiosk.firebase_uid})")
else:
    print(f"i  Kiosk already exists: {kiosk.kiosk_id} (firebase_uid: {kiosk.firebase_uid})")

print(f"   is_active: {kiosk.is_active}")
print(f"   bus: {kiosk.bus}")
print("\n✅ Kiosk is now pre-registered and ready for first login")
