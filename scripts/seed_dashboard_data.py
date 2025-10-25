#!/usr/bin/env python
"""
Seed database with realistic dashboard data for testing
Creates students, buses, routes, and boarding events
"""

from datetime import timedelta
from decimal import Decimal
import os
import sys

import django

# Setup Django
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bus_kiosk_backend.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone

from buses.models import Bus, Route
from events.models import BoardingEvent
from kiosks.models import Kiosk
from students.models import Parent, School, Student, StudentParent

User = get_user_model()


def seed_data():
    """Seed the database with test data"""
    print("[*] Starting database seeding...")

    # Get or create school
    school, created = School.objects.get_or_create(name="Imperial Academy")
    print(f"[+] School: {school.name} {'created' if created else 'exists'}")

    # Create buses with routes
    buses_data = [
        ("KA-01-AB-1234", "Route A - North Campus", 32),
        ("KA-01-AB-1235", "Route B - South Campus", 30),
        ("KA-01-AB-1236", "Route C - East Campus", 28),
        ("KA-01-AB-1237", "Route D - West Campus", 25),
        ("KA-01-AB-1238", "Route E - Central", 26),
        ("KA-01-AB-1239", "Route F - Downtown", 27),
    ]

    buses = {}
    for license_plate, route_name, capacity in buses_data:
        # Create route
        _route, _ = Route.objects.get_or_create(
            name=route_name,
            defaults={
                "description": f"Route serving {route_name.split(' - ')[1]}",
            },
        )

        # Create bus
        bus, created = Bus.objects.get_or_create(
            license_plate=license_plate,
            defaults={
                "capacity": capacity,
                "status": "active",
            },
        )
        buses[license_plate] = bus
        print(f"[+] Bus {license_plate} on {route_name}")

    # Create kiosks for each bus
    for license_plate, bus in buses.items():
        kiosk, _ = Kiosk.objects.get_or_create(
            kiosk_id=f"KIOSK-{license_plate[-4:]}",
            defaults={
                "bus": bus,
                "firmware_version": "v1.0.0",
                "is_active": True,
            },
        )

    # Create students
    students_data = [
        ("STU-2024-001", "Emma Johnson", "5", "A", "KA-01-AB-1234"),
        ("STU-2024-002", "Liam Smith", "5", "A", "KA-01-AB-1234"),
        ("STU-2024-003", "Olivia Williams", "4", "B", "KA-01-AB-1235"),
        ("STU-2024-004", "Noah Brown", "6", "C", "KA-01-AB-1236"),
        ("STU-2024-005", "Ava Davis", "3", "A", "KA-01-AB-1237"),
        ("STU-2024-006", "Ethan Martinez", "5", "B", "KA-01-AB-1238"),
        ("STU-2024-007", "Sophia Anderson", "4", "A", "KA-01-AB-1239"),
        ("STU-2024-008", "Mason Taylor", "6", "A", "KA-01-AB-1234"),
        ("STU-2024-009", "Isabella Garcia", "5", "C", "KA-01-AB-1235"),
        ("STU-2024-010", "Lucas Rodriguez", "4", "C", "KA-01-AB-1236"),
    ]

    students = []
    enrollment_date = timezone.now().date()
    for school_id, name, grade, section, bus_plate in students_data:
        # Note: In production, name should be encrypted
        student, created = Student.objects.get_or_create(
            school_student_id=school_id,  # School's student ID
            defaults={
                "name": name,  # This should be encrypted in production
                "school": school,
                "grade": grade,
                "section": section,
                "assigned_bus": buses[bus_plate],
                "status": "active",
                "enrollment_date": enrollment_date,
            },
        )
        students.append((student, school_id, bus_plate))
        print(f"[+] Student: {school_id} - {name}")

        # Create parent for each student
        parent_name = f"{name.split()[1]} (Parent)"
        parent, _ = Parent.objects.get_or_create(
            phone=f"+1-555-{1000 + len(students):04d}",
            defaults={
                "name": parent_name,
                "email": f"{name.split()[0].lower()}.parent@example.com",
            },
        )

        # Link parent to student
        StudentParent.objects.get_or_create(
            student=student,
            parent=parent,
            defaults={
                "relationship": "mother",
                "is_primary": True,
            },
        )
        print(f"  [+] Parent: {parent_name}")

    # Create boarding events
    now = timezone.now()
    morning_start = now.replace(hour=7, minute=0, second=0, microsecond=0)

    print("\n[*] Creating boarding events...")

    event_scenarios = [
        # (student_index, minutes_after_start, picked_up, dropped_off)
        (0, 15, True, True),  # Emma - completed
        (1, 20, True, False),  # Liam - in transit
        (2, 25, True, True),  # Olivia - completed
        (3, 5, True, False),  # Noah - delayed dropoff
        (4, None, False, False),  # Ava - not picked up yet
        (5, 10, True, True),  # Ethan - completed
        (6, None, False, False),  # Sophia - missed pickup (overdue)
        (7, 18, True, True),  # Mason - completed
        (8, 22, True, False),  # Isabella - in transit
        (9, 12, True, True),  # Lucas - completed
    ]

    for idx, (_student_tuple, pickup_offset, picked_up, dropped_off) in enumerate(event_scenarios[: len(students)]):
        student, school_id, bus_plate = students[idx]
        kiosk = Kiosk.objects.get(bus=buses[bus_plate])

        if picked_up:
            # Create pickup event
            pickup_time = morning_start + timedelta(minutes=pickup_offset)
            BoardingEvent.objects.get_or_create(
                student=student,
                kiosk_id=kiosk.kiosk_id,
                timestamp=pickup_time,
                defaults={
                    "confidence_score": Decimal("0.95"),
                    "bus_route": f"Route {bus_plate[-4]}",
                    "model_version": "v1.0",
                },
            )
            print(f"  [UP] Pickup: {school_id} at {pickup_time.strftime('%H:%M')}")

            if dropped_off:
                # Create dropoff event
                dropoff_time = pickup_time + timedelta(minutes=30)
                BoardingEvent.objects.get_or_create(
                    student=student,
                    kiosk_id=kiosk.kiosk_id,
                    timestamp=dropoff_time,
                    defaults={
                        "confidence_score": Decimal("0.96"),
                        "bus_route": f"Route {bus_plate[-4]}",
                        "model_version": "v1.0",
                    },
                )
                print(f"  [DOWN] Dropoff: {school_id} at {dropoff_time.strftime('%H:%M')}")

    print("\n[SUCCESS] Database seeding completed successfully!")
    print("[STATS] Created:")
    print("   - 1 School")
    print(f"   - {len(buses)} Buses")
    print(f"   - {len(students)} Students")
    print(f"   - {Parent.objects.count()} Parents")
    print(f"   - {BoardingEvent.objects.count()} Boarding Events")


if __name__ == "__main__":
    seed_data()
