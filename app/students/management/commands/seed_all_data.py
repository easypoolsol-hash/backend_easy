"""
Management command to seed all initial data for EasyPool system.

This command loads data from JSON files in /app/seed_data/ directory:
- schools.json: School information
- routes.json: Bus routes
- bus_stops.json: Bus stops for routes
- buses.json: Bus fleet
- kiosks.json: Kiosk devices
- sample_students.json: Sample students and parents

Usage:
    python manage.py seed_all_data
    python manage.py seed_all_data --clear  # Clear existing data first

For Google Cloud Run deployment:
    This can be run as a Cloud Run Job or as part of startup script
"""

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from buses.models import Bus, BusStop, Route, RouteStop
from kiosks.models import Kiosk
from students.models import Parent, School, Student, StudentParent


class Command(BaseCommand):
    help = "Seed all initial data from JSON files in seed_data directory"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing data before seeding (DESTRUCTIVE - use with caution)",
        )
        parser.add_argument(
            "--data-dir",
            type=str,
            default="/app/seed_data",
            help="Directory containing seed data files (default: /app/seed_data)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        clear_existing = options["clear"]
        data_dir = Path(options["data_dir"])

        if not data_dir.exists():
            self.stdout.write(self.style.ERROR(f"Seed data directory not found: {data_dir}"))
            self.stdout.write(self.style.WARNING("Expected directory structure:"))
            self.stdout.write("  /app/seed_data/")
            self.stdout.write("    ├── schools.json")
            self.stdout.write("    ├── routes.json")
            self.stdout.write("    ├── bus_stops.json")
            self.stdout.write("    ├── buses.json")
            self.stdout.write("    ├── kiosks.json")
            self.stdout.write("    └── sample_students.json")
            return

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 70))
        self.stdout.write(self.style.SUCCESS("  EasyPool Data Seeding - Industry Standard Pattern"))
        self.stdout.write(self.style.SUCCESS("=" * 70 + "\n"))

        if clear_existing:
            self._clear_existing_data()

        # Track created objects for foreign key resolution
        self.created_objects: dict[str, Any] = {}
        self.route_lookup: dict[str, Route] = {}
        self.bus_lookup: dict[str, Bus] = {}
        self.parent_lookup: dict[str, Parent] = {}

        # Load data in dependency order
        with transaction.atomic():
            self._load_schools(data_dir / "schools.json")
            self._load_routes(data_dir / "routes.json")
            self._load_bus_stops(data_dir / "bus_stops.json")
            self._load_buses(data_dir / "buses.json")
            self._load_kiosks(data_dir / "kiosks.json")
            self._load_students(data_dir / "sample_students.json")

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 70))
        self.stdout.write(self.style.SUCCESS("  Seeding Complete!"))
        self.stdout.write(self.style.SUCCESS("=" * 70))
        self._print_summary()

    def _clear_existing_data(self) -> None:
        """Clear all existing data (DESTRUCTIVE)"""
        self.stdout.write(self.style.WARNING("\n[WARNING]  CLEARING EXISTING DATA..."))

        # Clear data in reverse dependency order
        count, _ = StudentParent.objects.all().delete()
        if count > 0:
            self.stdout.write(f"  Deleted {count} Student-Parent relationships")

        count, _ = Student.objects.all().delete()
        if count > 0:
            self.stdout.write(f"  Deleted {count} Students")

        count, _ = Parent.objects.all().delete()
        if count > 0:
            self.stdout.write(f"  Deleted {count} Parents")

        count, _ = Kiosk.objects.all().delete()
        if count > 0:
            self.stdout.write(f"  Deleted {count} Kiosks")

        count, _ = Bus.objects.all().delete()
        if count > 0:
            self.stdout.write(f"  Deleted {count} Buses")

        count, _ = RouteStop.objects.all().delete()
        if count > 0:
            self.stdout.write(f"  Deleted {count} Route-Stop relationships")

        count, _ = BusStop.objects.all().delete()
        if count > 0:
            self.stdout.write(f"  Deleted {count} Bus Stops")

        count, _ = Route.objects.all().delete()
        if count > 0:
            self.stdout.write(f"  Deleted {count} Routes")

        count, _ = School.objects.all().delete()
        if count > 0:
            self.stdout.write(f"  Deleted {count} Schools")

        self.stdout.write(self.style.SUCCESS("[OK] Data cleared\n"))

    def _load_schools(self, file_path: Path) -> None:
        """Load schools from JSON"""
        if not file_path.exists():
            self.stdout.write(self.style.WARNING(f"[SKIP]  Skipping {file_path.name} (not found)"))
            return

        self.stdout.write(f"\n[SCHOOLS] Loading Schools from {file_path.name}...")

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        for item in data:
            fields = item["fields"]
            school, created = School.objects.get_or_create(name=fields["name"])
            self.created_objects["school"] = school
            status = "created" if created else "exists"
            self.stdout.write(f"  [OK] {school.name} ({status})")

    def _load_routes(self, file_path: Path) -> None:
        """Load routes from JSON"""
        if not file_path.exists():
            self.stdout.write(self.style.WARNING(f"[SKIP]  Skipping {file_path.name} (not found)"))
            return

        self.stdout.write(f"\n[ROUTES] Loading Routes from {file_path.name}...")

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        for item in data:
            fields = item["fields"]
            route, created = Route.objects.get_or_create(
                name=fields["name"],
                defaults={
                    "description": fields.get("description", ""),
                    "color_code": fields.get("color_code", "#0072B2"),
                    "line_pattern": fields.get("line_pattern", "solid"),
                    "is_active": fields.get("is_active", True),
                },
            )
            self.route_lookup[fields["name"]] = route
            status = "created" if created else "exists"
            self.stdout.write(f"  [OK] {route.name} ({status})")

    def _load_bus_stops(self, file_path: Path) -> None:
        """Load bus stops from JSON"""
        if not file_path.exists():
            self.stdout.write(self.style.WARNING(f"[SKIP]  Skipping {file_path.name} (not found)"))
            return

        self.stdout.write(f"\n[BUS STOPS] Loading Bus Stops from {file_path.name}...")

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        # Group stops by route
        stops_by_route: dict[str, list[Any]] = {}
        for item in data:
            route_ref = item.get("route_ref", "")
            if route_ref not in stops_by_route:
                stops_by_route[route_ref] = []
            stops_by_route[route_ref].append(item)

        # Create stops and route-stop relationships
        for route_name, stops in stops_by_route.items():
            route = self.route_lookup.get(route_name)
            if not route:
                self.stdout.write(self.style.WARNING(f"  [WARNING]  Route not found: {route_name}"))
                continue

            for sequence, item in enumerate(stops, start=1):
                fields = item["fields"]
                bus_stop, created = BusStop.objects.get_or_create(
                    name=fields["name"],
                    defaults={
                        "latitude": fields["latitude"],
                        "longitude": fields["longitude"],
                        "is_active": fields.get("is_active", True),
                    },
                )

                # Create route-stop relationship
                RouteStop.objects.get_or_create(
                    route=route,
                    bus_stop=bus_stop,
                    defaults={"sequence": sequence, "waypoints": []},
                )

                status = "created" if created else "exists"
                self.stdout.write(f"  [OK] {bus_stop.name} -> {route_name} (seq {sequence}) ({status})")

    def _load_buses(self, file_path: Path) -> None:
        """Load buses from JSON"""
        if not file_path.exists():
            self.stdout.write(self.style.WARNING(f"[SKIP]  Skipping {file_path.name} (not found)"))
            return

        self.stdout.write(f"\n[BUSES] Loading Buses from {file_path.name}...")

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        for item in data:
            fields = item["fields"]
            route_name = fields.get("route_name")
            route = self.route_lookup.get(route_name) if route_name else None

            bus, created = Bus.objects.get_or_create(
                bus_number=fields["bus_number"],
                defaults={
                    "license_plate": fields["license_plate"],
                    "route": route,
                    "capacity": fields.get("capacity", 40),
                    "device_id": fields.get("device_id"),
                    "status": fields.get("status", "active"),
                    "manufacturer": fields.get("manufacturer", ""),
                    "model": fields.get("model", ""),
                    "year": fields.get("year"),
                },
            )
            self.bus_lookup[fields["bus_number"]] = bus
            status = "created" if created else "exists"
            route_info = f"-> {route_name}" if route else ""
            self.stdout.write(f"  [OK] {bus.bus_number} ({bus.license_plate}) {route_info} ({status})")

    def _load_kiosks(self, file_path: Path) -> None:
        """Load kiosks from JSON"""
        if not file_path.exists():
            self.stdout.write(self.style.WARNING(f"[SKIP]  Skipping {file_path.name} (not found)"))
            return

        self.stdout.write(f"\n[KIOSKS] Loading Kiosks from {file_path.name}...")

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        for item in data:
            fields = item["fields"]
            bus_license = fields.get("bus_license_plate")
            bus = Bus.objects.filter(license_plate=bus_license).first() if bus_license else None

            kiosk, created = Kiosk.objects.get_or_create(
                kiosk_id=fields["kiosk_id"],
                defaults={
                    "bus": bus,
                    "firmware_version": fields.get("firmware_version", ""),
                    "is_active": fields.get("is_active", True),
                },
            )
            status = "created" if created else "exists"
            bus_info = f"-> {bus.bus_number}" if bus else ""
            self.stdout.write(f"  [OK] {kiosk.kiosk_id} {bus_info} ({status})")

    def _load_students(self, file_path: Path) -> None:
        """Load students and parents from JSON"""
        if not file_path.exists():
            self.stdout.write(self.style.WARNING(f"[SKIP]  Skipping {file_path.name} (not found)"))
            return

        self.stdout.write(f"\n[STUDENTS] Loading Parents and Students from {file_path.name}...")

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        school = self.created_objects.get("school")
        if not school:
            self.stdout.write(self.style.ERROR("  [ERROR] No school found - cannot create students"))
            return

        # First pass: Create parents
        for item in data:
            if item["model"] == "students.parent":
                fields = item["fields"]
                ref = item.get("ref")

                # Check if parent already exists by phone
                try:
                    # Create parent with temp values first
                    parent = Parent.objects.create(
                        phone="temp_phone",
                        email="temp_email",
                        name="temp_name",
                    )
                    # Then set encrypted values (which validates and encrypts)
                    parent.encrypted_phone = fields["phone"]
                    parent.encrypted_email = fields["email"]
                    parent.encrypted_name = fields["name"]
                    parent.save()

                    if ref:
                        self.parent_lookup[ref] = parent

                    self.stdout.write(f"  [OK] Parent: {fields['name']} (created)")
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"  [WARNING]  Parent creation failed: {e}"))

        # Second pass: Create students
        for item in data:
            if item["model"] == "students.student":
                fields = item["fields"]
                bus_number = fields.get("assigned_bus_number")
                bus = self.bus_lookup.get(bus_number) if bus_number else None
                parent_ref = fields.get("parent_ref")
                student_parent: Parent | None = self.parent_lookup.get(parent_ref) if parent_ref else None

                try:
                    # Parse enrollment date
                    enrollment_date = datetime.fromisoformat(fields["enrollment_date"]).date()

                    # Create student with temp name first
                    student = Student.objects.create(
                        school=school,
                        school_student_id=fields["school_student_id"],
                        name="temp_name",
                        grade=fields.get("grade", ""),
                        section=fields.get("section", ""),
                        address_latitude=fields.get("address_latitude"),
                        address_longitude=fields.get("address_longitude"),
                        assigned_bus=bus,
                        status=fields.get("status", "active"),
                        enrollment_date=enrollment_date,
                    )
                    # Then set encrypted name
                    student.encrypted_name = fields["name"]
                    student.save()

                    bus_info = f"-> {bus.bus_number}" if bus else ""
                    self.stdout.write(f"  [OK] Student: {fields['name']} {bus_info} (created)")

                    # Link student to parent if available
                    if student_parent:
                        StudentParent.objects.create(
                            student=student,
                            parent=student_parent,
                            relationship="father",  # Default - can be customized
                            is_primary=True,
                        )
                        self.stdout.write(f"     └─ Linked to parent: {student_parent.encrypted_name}")

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  [ERROR] Student creation failed: {e}"))

    def _print_summary(self) -> None:
        """Print summary of seeded data"""
        self.stdout.write("\n[DATA SUMMARY]")
        self.stdout.write(f"  Schools:       {School.objects.count()}")
        self.stdout.write(f"  Routes:        {Route.objects.count()}")
        self.stdout.write(f"  Bus Stops:     {BusStop.objects.count()}")
        self.stdout.write(f"  Buses:         {Bus.objects.count()}")
        self.stdout.write(f"  Kiosks:        {Kiosk.objects.count()}")
        self.stdout.write(f"  Parents:       {Parent.objects.count()}")
        self.stdout.write(f"  Students:      {Student.objects.count()}")
        self.stdout.write("")
