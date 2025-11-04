"""
Django management command to seed boarding events with encrypted PII data
Run: docker-compose exec web python manage.py seed_boarding_events

Creates realistic boarding events for testing the frontend dashboard
"""

from datetime import timedelta
import random
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from buses.models import Bus
from events.models import BoardingEvent
from kiosks.models import Kiosk
from students.models import Student


class Command(BaseCommand):
    help = "Seed boarding events with encrypted PII data for frontend testing"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--count",
            type=int,
            default=50,
            help="Number of boarding events to create (default: 50)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing boarding events before seeding",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        count = options["count"]
        clear_existing = options["clear"]

        if clear_existing:
            deleted_count = BoardingEvent.objects.all().delete()[0]
            self.stdout.write(self.style.WARNING(f"Deleted {deleted_count} existing boarding events"))

        # Get students, buses, kiosks
        students = list(Student.objects.all())
        buses = list(Bus.objects.all())
        kiosks = list(Kiosk.objects.all())

        if not students:
            self.stdout.write(self.style.ERROR("No students found. Run 'seed_data' first."))
            return

        if not kiosks:
            self.stdout.write(self.style.ERROR("No kiosks found. Run 'seed_data' first."))
            return

        self.stdout.write(f"\nSeeding {count} boarding events...")
        self.stdout.write(f"  Students: {len(students)}")
        self.stdout.write(f"  Buses: {len(buses)}")
        self.stdout.write(f"  Kiosks: {len(kiosks)}")
        self.stdout.write("")

        now = timezone.now()
        created_events = []

        # Create events for the last 7 days, with emphasis on today
        for i in range(count):
            # Random student
            student = random.choice(students)

            # Random kiosk
            kiosk = random.choice(kiosks)

            # 70% chance for today, 30% for past days (more recent data)
            if random.random() < 0.7:
                # Today's events (within last 12 hours)
                days_ago = 0
                hours_ago = random.randint(0, 12)
                minutes_ago = random.randint(0, 59)
            else:
                # Past days (1-7 days ago)
                days_ago = random.randint(1, 7)
                hours_ago = random.randint(0, 23)
                minutes_ago = random.randint(0, 59)

            event_time = now - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)

            # High confidence score for face recognition
            confidence = random.uniform(0.85, 0.99)

            # Random GPS coordinates (example: Bangalore area)
            latitude = 12.9716 + random.uniform(-0.1, 0.1)
            longitude = 77.5946 + random.uniform(-0.1, 0.1)

            # Bus route from kiosk's bus
            bus_route = kiosk.bus.route.name if kiosk.bus and kiosk.bus.route else "Unknown"

            # Create boarding event
            event = BoardingEvent.objects.create(
                student=student,
                kiosk_id=kiosk.kiosk_id,
                confidence_score=confidence,
                timestamp=event_time,
                latitude=latitude,
                longitude=longitude,
                bus_route=bus_route,
                model_version="insightface-v2.1",
                metadata={
                    "device_model": "Raspberry Pi 4",
                    "camera_id": f"CAM-{random.randint(1, 5)}",
                    "processing_time_ms": random.randint(100, 500),
                },
            )

            created_events.append(event)

            if (i + 1) % 10 == 0:
                self.stdout.write(f"  Created {i + 1}/{count} events...")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"[OK] Successfully created {len(created_events)} boarding events"))

        # Show recent events summary
        self.stdout.write("\nRecent boarding events (last 5):")
        recent_events = BoardingEvent.objects.order_by("-timestamp")[:5]
        for event in recent_events:
            # Note: student name is encrypted, backend will decrypt for API response
            student_id_str = str(event.student.student_id)
            self.stdout.write(
                f"  {event.timestamp.strftime('%Y-%m-%d %H:%M')} - "
                f"Student {student_id_str[:8]}... - "
                f"Confidence: {event.confidence_score:.2f} - "
                f"Kiosk: {event.kiosk_id}"
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("[OK] Boarding events seeded successfully!"))
        self.stdout.write("\n[INFO] Frontend can now fetch real data using OpenAPI client")
        self.stdout.write("   Operation ID: apiV1BoardingEventsList")
        self.stdout.write("   PII data is encrypted in DB, decrypted in serializer")
