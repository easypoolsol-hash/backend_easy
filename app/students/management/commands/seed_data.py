"""
Django management command to seed test data
Run: docker-compose exec web python manage.py seed_data

Dataset structure:
  seed_data/
    dataset/
      student_name/
        photo1.jpg  # first alphabetically = primary
        photo2.jpg
        photo3.jpg
"""

from datetime import datetime
from datetime import timezone as dt_timezone
import json
from pathlib import Path
import random
from typing import Any, cast

from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils import timezone

from buses.models import Bus, Route
from kiosks.models import Kiosk
from students.models import FaceEmbeddingMetadata, Parent, School, Student, StudentPhoto


class Command(BaseCommand):
    help = "Seed test data from test_data.json and load photos from dataset folder"

    def handle(self, *args, **options):
        seed_path = Path("/app/seed_data/test_data.json")
        dataset_path = Path("/app/seed_data/dataset")

        if not seed_path.exists():
            self.stdout.write(self.style.ERROR(f"Seed file not found: {seed_path}"))
            return

        with open(seed_path, encoding="utf-8") as seed_f:
            data = json.load(seed_f)

        created_objects: dict[str, Any] = {}

        for item in data:
            model_name = item.get("model")
            fields = item.get("fields", {})

            if model_name == "students.school":
                school_obj, created = School.objects.get_or_create(
                    name=fields.get("name"),
                    defaults={"address": fields.get("address", "")},
                )
                created_objects["school"] = school_obj
                self.stdout.write(
                    f"[OK] School: {school_obj.name} ({'created' if created else 'exists'})"
                )

            elif model_name == "buses.route":
                route_obj, created = Route.objects.get_or_create(
                    name=fields.get("name"),
                    defaults={
                        "school": created_objects.get("school"),
                        "start_time": fields.get("start_time"),
                        "end_time": fields.get("end_time"),
                    },
                )
                created_objects["route"] = route_obj
                self.stdout.write(
                    f"[OK] Route: {route_obj.name} ({'created' if created else 'exists'})"
                )

            elif model_name == "buses.bus":
                license_plate = fields.get("license_plate")
                bus_obj, created = Bus.objects.get_or_create(
                    license_plate=license_plate,
                    defaults={
                        "route": created_objects.get("route"),
                        "capacity": fields.get("capacity", 40),
                        "status": fields.get("status", "active"),
                    },
                )
                created_objects["bus"] = bus_obj
                self.stdout.write(
                    f"[OK] Bus: {bus_obj.license_plate} ({'created' if created else 'exists'})"
                )

            elif model_name == "kiosks.kiosk":
                kiosk_obj, created = Kiosk.objects.update_or_create(
                    bus=created_objects.get("bus"),
                    defaults={
                        "kiosk_id": fields.get("kiosk_id"),
                        "is_active": fields.get("is_active", True),
                    },
                )
                created_objects["kiosk"] = kiosk_obj
                self.stdout.write(
                    f"[OK] Kiosk: {kiosk_obj.kiosk_id} ({'created' if created else 'exists'})"
                )

            elif model_name == "students.parent":
                parent_obj = Parent.objects.first()
                if not parent_obj:
                    parent_obj = Parent.objects.create(
                        phone="temp_phone", email="temp_email", name="temp_name"
                    )
                    parent_obj.encrypted_phone = fields.get("phone", "")
                    parent_obj.encrypted_email = fields.get("email", "")
                    parent_obj.encrypted_name = fields.get("name", "")
                    parent_obj.save()
                    created = True
                else:
                    created = False
                created_objects["parent"] = parent_obj
                self.stdout.write(
                    f"[OK] Parent: {parent_obj.encrypted_name} ({'created' if created else 'exists'})"
                )

            elif model_name == "students.student":
                student_obj = Student.objects.filter(
                    school=cast(School, created_objects.get("school"))
                ).first()
                if not student_obj:
                    student_obj = Student.objects.create(
                        school=cast(School, created_objects.get("school")),
                        name="temp_name",
                        grade=fields.get("grade", ""),
                        section=fields.get("section", ""),
                        assigned_bus=cast(Bus, created_objects.get("bus")),
                        status=fields.get("status", "active"),
                    )
                    student_obj.encrypted_name = fields.get("name", "")
                    student_obj.save()
                    created = True
                else:
                    created = False
                created_objects["student"] = student_obj
                self.stdout.write(
                    f"[OK] Student: {student_obj.encrypted_name} ({'created' if created else 'exists'})"
                )

            elif model_name == "students.studentphoto":
                # Get student folder from dataset
                student = created_objects.get("student")
                if student is None:
                    self.stdout.write(
                        self.style.WARNING("[SKIP] No student available for photos")
                    )
                    continue
                student_folder_name = fields.get("student_folder", "")

                if not student_folder_name:
                    self.stdout.write(
                        self.style.WARNING(
                            "[SKIP] No student_folder specified for photos"
                        )
                    )
                    continue

                student_folder = dataset_path / student_folder_name

                if not student_folder.exists():
                    self.stdout.write(
                        self.style.ERROR(
                            f"[ERROR] Student folder not found: {student_folder}"
                        )
                    )
                    continue

                # Get all image files from student folder
                image_extensions = {".jpg", ".jpeg", ".png", ".webp"}
                photo_files = sorted(
                    [
                        f
                        for f in student_folder.iterdir()
                        if f.suffix.lower() in image_extensions
                    ]
                )

                if not photo_files:
                    self.stdout.write(
                        self.style.WARNING(
                            f"[SKIP] No photos found in {student_folder}"
                        )
                    )
                    continue

                # Delete existing photos for this student
                StudentPhoto.objects.filter(student=student).delete()

                # Upload all photos (first = primary)
                for idx, photo_file in enumerate(photo_files):
                    is_primary = idx == 0  # First photo is primary

                    photo_obj = StudentPhoto(
                        student=student,
                        is_primary=is_primary,
                        captured_at=timezone.now(),
                    )
                    with open(photo_file, "rb") as photo_f:
                        # `photo_f` is a binary file (BufferedReader); cast to Any for Django File
                        _f = cast(Any, photo_f)
                        photo_obj.photo.save(photo_file.name, File(_f), save=True)

                    primary_label = " (PRIMARY)" if is_primary else ""
                    msg = f"[OK] Photo {idx + 1}/{len(photo_files)}: {photo_obj.photo.name}{primary_label}"
                    self.stdout.write(self.style.SUCCESS(msg))

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Total photos for {student.encrypted_name}: {len(photo_files)}\n"
                    )
                )

            elif model_name == "students.faceembeddingmetadata":
                # Create a FaceEmbeddingMetadata entry linked to the student's primary photo
                student = created_objects.get("student")
                if not student:
                    self.stdout.write(
                        self.style.WARNING("[SKIP] No student available for embedding")
                    )
                    continue

                primary_photo = StudentPhoto.objects.filter(
                    student=student, is_primary=True
                ).first()
                if not primary_photo:
                    self.stdout.write(
                        self.style.WARNING(
                            "[SKIP] No primary photo found for student to attach embedding"
                        )
                    )
                    continue

                # Extract fields from fixture
                model_name_field = fields.get("model_name", "unknown")
                model_version = fields.get("model_version", "v1")
                embedding = [
                    random.uniform(-1, 1) for _ in range(128)  # nosec B311
                ]  # Generate random 128-dim embedding
                quality_score = fields.get("quality_score", 0.0)
                is_primary = fields.get("is_primary", False)
                captured_at_raw = fields.get("captured_at")

                # Parse captured_at if provided, otherwise use now()
                try:
                    if captured_at_raw:
                        # timezone-aware parsing using standard library
                        captured_at = datetime.fromisoformat(
                            captured_at_raw.replace("Z", "+00:00")
                        )
                        # Make timezone-aware if naive
                        if captured_at.tzinfo is None:
                            from django.utils import timezone as dj_tz

                            captured_at = dj_tz.make_aware(captured_at, dt_timezone.utc)
                    else:
                        captured_at = timezone.now()
                except Exception:
                    captured_at = timezone.now()

                fem = FaceEmbeddingMetadata(
                    student_photo=primary_photo,
                    model_name=model_name_field,
                    model_version=model_version,
                    embedding=embedding,
                    quality_score=quality_score,
                    is_primary=is_primary,
                    captured_at=captured_at,
                )
                fem.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[OK] Seeded face embedding for {student.encrypted_name}"
                    )
                )

        self.stdout.write(self.style.SUCCESS("\n=== Seed complete! ==="))
