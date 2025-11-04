"""
Management command to seed bus location data for real-time tracking.

Creates mock GPS location data for active buses to enable WebSocket testing
and map visualization. Generates current location plus historical trail.

Usage:
    python manage.py seed_bus_locations
    python manage.py seed_bus_locations --count 10  # Generate 10 historical points per bus
    python manage.py seed_bus_locations --clear  # Clear existing locations first
"""

from datetime import timedelta
import random
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from buses.models import Bus
from kiosks.models import BusLocation


class Command(BaseCommand):
    help = "Seed bus location data for real-time tracking"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--count",
            type=int,
            default=6,
            help="Number of historical location points per bus (default: 6)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing bus locations before seeding",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        count = options["count"]
        clear_existing = options["clear"]

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 70))
        self.stdout.write(self.style.SUCCESS("  Bus Location Seeding"))
        self.stdout.write(self.style.SUCCESS("=" * 70 + "\n"))

        if clear_existing:
            deleted_count, _ = BusLocation.objects.all().delete()
            self.stdout.write(f"[CLEAR] Deleted {deleted_count} existing bus locations\n")

        # Get all active buses with kiosks
        buses_with_kiosks = Bus.objects.filter(kiosk__isnull=False, status="active").select_related(
            "kiosk",
            "route",
        )

        if not buses_with_kiosks.exists():
            self.stdout.write(self.style.WARNING("[WARNING] No active buses with kiosks found"))
            self.stdout.write("  Run 'python manage.py seed_all_data' first to create buses and kiosks")
            return

        locations_created = 0
        now = timezone.now()

        self.stdout.write(f"[BUS LOCATIONS] Creating {count} location points for each bus...\n")

        for bus in buses_with_kiosks:
            kiosk = bus.kiosk

            # Get route stops to generate realistic location data
            route_stops = []
            if bus.route:
                route_stops = list(bus.route.route_stops.all().select_related("bus_stop").order_by("sequence"))

            if not route_stops or len(route_stops) < 2:
                self.stdout.write(self.style.WARNING(f"  [SKIP] {bus.bus_number}: no route or insufficient stops (need at least 2)"))
                continue

            # Extract lat/lon from stops (convert Decimal to float)
            stops = [(float(rs.bus_stop.latitude), float(rs.bus_stop.longitude)) for rs in route_stops]
            start_lat, start_lon = stops[0]
            end_lat, end_lon = stops[-1]

            # Generate random progress along route (0.0 = start, 1.0 = end)
            current_progress = random.uniform(0.2, 0.8)

            # Create current location and historical trail
            for i in range(count):
                # Calculate progress (going backwards in time)
                progress = max(0.0, current_progress - (i * 0.05))
                timestamp = now - timedelta(minutes=i)

                # Interpolate position along route
                if len(stops) == 2:
                    # Simple linear interpolation between start and end
                    lat = start_lat + (end_lat - start_lat) * progress
                    lon = start_lon + (end_lon - start_lon) * progress
                else:
                    # Multi-segment interpolation
                    segment_length = 1.0 / (len(stops) - 1)
                    segment_index = int(progress / segment_length)
                    segment_index = min(segment_index, len(stops) - 2)  # Ensure valid index

                    segment_start = stops[segment_index]
                    segment_end = stops[segment_index + 1]
                    segment_progress = (progress - segment_index * segment_length) / segment_length

                    lat = segment_start[0] + (segment_end[0] - segment_start[0]) * segment_progress
                    lon = segment_start[1] + (segment_end[1] - segment_start[1]) * segment_progress

                # Add GPS noise for realism
                lat += random.uniform(-0.0005, 0.0005)
                lon += random.uniform(-0.0005, 0.0005)

                # Create location point
                BusLocation.objects.create(
                    kiosk=kiosk,
                    latitude=lat,
                    longitude=lon,
                    accuracy=random.uniform(5, 20),  # 5-20 meters
                    speed=random.uniform(15, 45),  # 15-45 km/h (city traffic)
                    heading=random.uniform(0, 360),
                    timestamp=timestamp,
                )
                locations_created += 1

            self.stdout.write(f"  [OK] {bus.bus_number} ({bus.license_plate}): {count} location points created")

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 70))
        self.stdout.write(self.style.SUCCESS(f"  Seeding Complete! Created {locations_created} locations"))
        self.stdout.write(self.style.SUCCESS("=" * 70))

        self.stdout.write("\n[INFO] Real-time tracking endpoints:")
        self.stdout.write("  WebSocket: ws://localhost:8000/ws/bus-tracking/")
        self.stdout.write("  REST API:  http://localhost:8000/api/v1/bus-locations/")
        self.stdout.write("")
