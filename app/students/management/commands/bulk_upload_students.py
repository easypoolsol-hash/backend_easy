"""
Bulk upload students from ZIP file containing CSV and face images.

Usage:
    python manage.py bulk_upload_students /path/to/upload_data.zip --school-id <uuid>

CSV Format:
    Sr.No,admission_no,Student Name,Class Section,Bus Number,Pickup Route,Pickup Bus Stop Name,Drop Route,Drop Bus Stop Name

ZIP Structure:
    upload_data.zip
    ├── students.csv
    └── student_folders/
        ├── 220037/
        │   ├── photo1.jpg
        │   └── photo2.jpg
        └── 220221/
            └── photo1.jpg
"""

import csv
from decimal import Decimal
import io
import os
import zipfile

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from buses.models import Bus, BusStop
from students.models import School, Student, StudentPhoto


class Command(BaseCommand):
    help = "Bulk upload students from ZIP file with CSV and face images"

    def add_arguments(self, parser):
        parser.add_argument("zip_file", type=str, help="Path to ZIP file containing students.csv and student_folders/")
        parser.add_argument("--school-id", type=str, required=True, help="School UUID")
        parser.add_argument("--dry-run", action="store_true", help="Preview what would be uploaded without saving")

    def handle(self, *args, **options):
        zip_path = options["zip_file"]
        school_id = options["school_id"]
        dry_run = options.get("dry_run", False)

        # Validate school exists
        try:
            school = School.objects.get(school_id=school_id)
            self.stdout.write(self.style.SUCCESS(f"[OK] School found: {school.name}"))
        except School.DoesNotExist as e:
            raise CommandError(f"School with ID {school_id} not found") from e

        # Validate ZIP file exists
        if not os.path.exists(zip_path):
            raise CommandError(f"ZIP file not found: {zip_path}")

        self.stdout.write(self.style.NOTICE(f"\n{'=' * 60}"))
        self.stdout.write(self.style.NOTICE("BULK UPLOAD STUDENTS"))
        self.stdout.write(self.style.NOTICE(f"{'=' * 60}\n"))

        # Process ZIP file
        stats = {
            "students_created": 0,
            "students_updated": 0,
            "students_without_bus": [],
            "photos_uploaded": 0,
            "buses_found": {},
            "buses_missing": [],
            "bus_stops_found": [],
            "bus_stops_created": [],
            "errors": [],
        }

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_file:
                # Read CSV
                csv_content = self._read_csv_from_zip(zip_file)
                reader = csv.DictReader(io.StringIO(csv_content))

                self.stdout.write(self.style.NOTICE("[PROCESSING] students...\n"))

                for row in reader:
                    try:
                        self._process_student_row(row, school, zip_file, stats, dry_run)
                    except Exception as e:
                        error_msg = f"Row {row.get('Sr.No', '?')}: {e!s}"
                        stats["errors"].append(error_msg)
                        self.stdout.write(self.style.ERROR(f"[X] {error_msg}"))

        except zipfile.BadZipFile as e:
            raise CommandError("Invalid ZIP file") from e

        # Print summary report
        self._print_summary(stats, dry_run)

        if stats["errors"]:
            self.stdout.write(self.style.ERROR(f"\n[!] {len(stats['errors'])} errors occurred"))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] No changes were saved"))
        else:
            self.stdout.write(self.style.SUCCESS("\n[OK] Upload completed successfully!"))

    def _read_csv_from_zip(self, zip_file):
        """Read students.csv from ZIP file"""
        try:
            with zip_file.open("students.csv") as csv_file:
                return csv_file.read().decode("utf-8")
        except KeyError as e:
            raise CommandError("students.csv not found in ZIP file") from e

    def _process_student_row(self, row, school, zip_file, stats, dry_run):
        """Process a single student row from CSV"""
        admission_no = row.get("admission_no", "").strip()
        student_name = row.get("Student Name", "").strip()
        class_section = row.get("Class Section", "").strip()
        bus_number = row.get("Bus Number", "").strip()
        pickup_stop_name = row.get("Pickup Bus Stop Name", "").strip()
        drop_stop_name = row.get("Drop Bus Stop Name", "").strip()

        if not admission_no or not student_name:
            raise ValueError("Missing admission_no or Student Name")

        # Parse grade and section from "II - A" format
        grade, section = self._parse_class_section(class_section)

        # Lookup bus (SAFE: don't fail if missing, just don't assign)
        assigned_bus = None
        if bus_number:
            try:
                assigned_bus = Bus.objects.get(bus_number=bus_number)
                if bus_number not in stats["buses_found"]:
                    stats["buses_found"][bus_number] = assigned_bus.license_plate
            except Bus.DoesNotExist:
                # SAFE APPROACH: Log as missing but continue upload
                if bus_number not in stats["buses_missing"]:
                    stats["buses_missing"].append(bus_number)
                assigned_bus = None

        # Handle bus stops (auto-create inactive if missing)
        self._get_or_create_bus_stop(pickup_stop_name, stats, dry_run)
        self._get_or_create_bus_stop(drop_stop_name, stats, dry_run)

        if dry_run:
            self.stdout.write(f"  [DRY-RUN] Would process: {admission_no} - {student_name}")
            stats["students_created"] += 1
            return

        # Encrypt student name
        fernet = Fernet(settings.ENCRYPTION_KEY.encode())
        encrypted_name = fernet.encrypt(student_name.encode()).decode()

        # Create or update student
        student, created = Student.objects.update_or_create(
            school_student_id=admission_no,
            defaults={
                "school": school,
                "name": encrypted_name,
                "grade": grade,
                "section": section,
                "assigned_bus": assigned_bus,
                "status": "active",
            },
        )

        if created:
            stats["students_created"] += 1
            status_msg = f"  [+] Created: {admission_no} - {student_name}"
            if not assigned_bus and bus_number:
                status_msg += f" [!] No bus - {bus_number} not found"
                stats["students_without_bus"].append(f"{admission_no} ({bus_number})")
            self.stdout.write(self.style.SUCCESS(status_msg))
        else:
            stats["students_updated"] += 1
            status_msg = f"  [~] Updated: {admission_no} - {student_name}"
            if not assigned_bus and bus_number:
                status_msg += f" [!] No bus - {bus_number} not found"
                if f"{admission_no} ({bus_number})" not in stats["students_without_bus"]:
                    stats["students_without_bus"].append(f"{admission_no} ({bus_number})")
            self.stdout.write(self.style.WARNING(status_msg))

        # Upload student photos
        photo_count = self._upload_student_photos(student, admission_no, zip_file, stats)
        if photo_count > 0:
            self.stdout.write(f"    [PHOTO] Uploaded {photo_count} photo(s)")

    def _parse_class_section(self, class_section):
        """Parse 'II - A' into grade='2' and section='A'"""
        if not class_section:
            return "", ""

        parts = class_section.split("-")
        if len(parts) == 2:
            grade_roman = parts[0].strip()
            section = parts[1].strip()

            # Convert Roman numerals to numbers (basic mapping)
            roman_to_num = {
                "I": "1",
                "II": "2",
                "III": "3",
                "IV": "4",
                "V": "5",
                "VI": "6",
                "VII": "7",
                "VIII": "8",
                "IX": "9",
                "X": "10",
                "XI": "11",
                "XII": "12",
                "IG 10": "IG 10",
            }
            grade = roman_to_num.get(grade_roman, grade_roman)
            return grade, section

        return class_section, ""

    def _get_or_create_bus_stop(self, stop_name, stats, dry_run):
        """Get existing bus stop or create as INACTIVE"""
        if not stop_name:
            return None

        if dry_run:
            return None

        bus_stop, created = BusStop.objects.get_or_create(
            name=stop_name,
            defaults={
                "latitude": Decimal("0.0"),
                "longitude": Decimal("0.0"),
                "is_active": False,  # INACTIVE until admin reviews
            },
        )

        if created:
            if stop_name not in stats["bus_stops_created"]:
                stats["bus_stops_created"].append(stop_name)
        else:
            if stop_name not in stats["bus_stops_found"]:
                stats["bus_stops_found"].append(stop_name)

        return bus_stop

    def _upload_student_photos(self, student, admission_no, zip_file, stats):
        """Upload photos from student_folders/{admission_no}/ directory"""
        photo_count = 0
        student_folder = f"student_folders/{admission_no}/"

        # List all files in student's folder
        photo_files = [f for f in zip_file.namelist() if f.startswith(student_folder) and not f.endswith("/")]

        for idx, photo_path in enumerate(photo_files):
            try:
                with zip_file.open(photo_path) as photo_file:
                    photo_data = photo_file.read()

                    # Determine content type
                    ext = os.path.splitext(photo_path)[1].lower()
                    content_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png"

                    # Create StudentPhoto
                    StudentPhoto.objects.create(
                        student=student,
                        photo_data=photo_data,
                        photo_content_type=content_type,
                        is_primary=(idx == 0),  # First photo is primary
                    )

                    photo_count += 1
                    stats["photos_uploaded"] += 1

            except Exception as e:
                stats["errors"].append(f"Photo upload failed for {admission_no}/{photo_path}: {e!s}")

        return photo_count

    def _print_summary(self, stats, dry_run):
        """Print upload summary report"""
        self.stdout.write(self.style.NOTICE(f"\n{'=' * 60}"))
        self.stdout.write(self.style.NOTICE("UPLOAD SUMMARY"))
        self.stdout.write(self.style.NOTICE(f"{'=' * 60}\n"))

        # Students
        self.stdout.write(self.style.SUCCESS(f"[+] Students created: {stats['students_created']}"))
        self.stdout.write(self.style.WARNING(f"[~] Students updated: {stats['students_updated']}"))
        self.stdout.write(self.style.SUCCESS(f"[PHOTO] Photos uploaded: {stats['photos_uploaded']}"))

        # Buses
        if stats["buses_found"]:
            self.stdout.write(self.style.SUCCESS(f"\n[BUS] Buses found ({len(stats['buses_found'])}):"))
            for bus_num, license_plate in stats["buses_found"].items():
                self.stdout.write(f"  [+] {bus_num} ({license_plate})")

        if stats["buses_missing"]:
            self.stdout.write(self.style.ERROR(f"\n[!] Buses NOT found ({len(stats['buses_missing'])}):"))
            for bus_num in stats["buses_missing"]:
                self.stdout.write(f"  [X] {bus_num} - Create this bus and assign students later!")

        if stats["students_without_bus"]:
            self.stdout.write(self.style.WARNING(f"\n[!] Students uploaded WITHOUT bus assignment ({len(stats['students_without_bus'])}):"))
            for student_info in stats["students_without_bus"][:10]:
                self.stdout.write(f"  [!] {student_info}")
            if len(stats["students_without_bus"]) > 10:
                self.stdout.write(f"  ... and {len(stats['students_without_bus']) - 10} more")
            self.stdout.write("\n  [*] Action needed: Create missing buses, then assign in admin panel")

        # Bus Stops
        if stats["bus_stops_found"]:
            self.stdout.write(self.style.SUCCESS(f"\n[STOP] Bus stops found ({len(stats['bus_stops_found'])}):"))
            for stop in stats["bus_stops_found"][:5]:
                self.stdout.write(f"  [+] {stop}")
            if len(stats["bus_stops_found"]) > 5:
                self.stdout.write(f"  ... and {len(stats['bus_stops_found']) - 5} more")

        if stats["bus_stops_created"]:
            self.stdout.write(self.style.WARNING(f"\n[NEW] Bus stops created as INACTIVE ({len(stats['bus_stops_created'])}):"))
            for stop in stats["bus_stops_created"]:
                self.stdout.write(f"  [!] {stop} - Needs admin review (add lat/long, activate)")
