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

import json
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils import timezone

from buses.models import Bus, Route
from kiosks.models import Kiosk
from students.models import Parent, School, Student, StudentPhoto


class Command(BaseCommand):
    help = "Seed test data from test_data.json and load photos from dataset folder"

    def handle(self, *args, **options):
        seed_path = Path("/app/seed_data/test_data.json")
        dataset_path = Path("/app/seed_data/dataset")

        if not seed_path.exists():
            self.stdout.write(self.style.ERROR(f"Seed file not found: {seed_path}"))
            return

        with open(seed_path, "r") as f:
            data = json.load(f)

        created_objects = {}

        for item in data:
            model_name = item.get("model")
            fields = item.get("fields", {})

            if model_name == "students.school":
                obj, created = School.objects.get_or_create(
                    name=fields.get("name"), defaults={"address": fields.get("address", "")}
                )
                created_objects["school"] = obj
                self.stdout.write(f"[OK] School: {obj.name} ({'created' if created else 'exists'})")

            elif model_name == "buses.route":
                obj, created = Route.objects.get_or_create(
                    name=fields.get("name"),
                    defaults={
                        "school": created_objects.get("school"),
                        "start_time": fields.get("start_time"),
                        "end_time": fields.get("end_time"),
                    },
                )
                created_objects["route"] = obj
                self.stdout.write(f"[OK] Route: {obj.name} ({'created' if created else 'exists'})")

            elif model_name == "buses.bus":
                license_plate = fields.get("license_plate")
                obj, created = Bus.objects.get_or_create(
                    license_plate=license_plate,
                    defaults={
                        "route": created_objects.get("route"),
                        "capacity": fields.get("capacity", 40),
                        "status": fields.get("status", "active"),
                    },
                )
                created_objects["bus"] = obj
                self.stdout.write(
                    f"[OK] Bus: {obj.license_plate} ({'created' if created else 'exists'})"
                )

            elif model_name == "kiosks.kiosk":
                obj, created = Kiosk.objects.get_or_create(
                    kiosk_id=fields.get("kiosk_id"),
                    defaults={
                        "bus": created_objects.get("bus"),
                        "location": fields.get("location", "Test Bus"),
                        "is_active": fields.get("is_active", True),
                    },
                )
                created_objects["kiosk"] = obj
                self.stdout.write(
                    f"[OK] Kiosk: {obj.kiosk_id} ({'created' if created else 'exists'})"
                )

            elif model_name == "students.parent":
                obj = Parent.objects.first()
                if not obj:
                    obj = Parent.objects.create(
                        phone="temp_phone", email="temp_email", name="temp_name"
                    )
                    obj.encrypted_phone = fields.get("phone", "")
                    obj.encrypted_email = fields.get("email", "")
                    obj.encrypted_name = fields.get("name", "")
                    obj.save()
                    created = True
                else:
                    created = False
                created_objects["parent"] = obj
                self.stdout.write(
                    f"[OK] Parent: {obj.encrypted_name} ({'created' if created else 'exists'})"
                )

            elif model_name == "students.student":
                obj = Student.objects.filter(school=created_objects.get("school")).first()
                if not obj:
                    obj = Student.objects.create(
                        school=created_objects.get("school"),
                        name="temp_name",
                        grade=fields.get("grade", ""),
                        section=fields.get("section", ""),
                        assigned_bus=created_objects.get("bus"),
                        status=fields.get("status", "active"),
                        date_of_birth=fields.get("date_of_birth"),
                    )
                    obj.encrypted_name = fields.get("name", "")
                    obj.save()
                    created = True
                else:
                    created = False
                created_objects["student"] = obj
                self.stdout.write(
                    f"[OK] Student: {obj.encrypted_name} ({'created' if created else 'exists'})"
                )

            elif model_name == "students.studentphoto":
                # Get student folder from dataset
                student = created_objects.get("student")
                student_folder_name = fields.get("student_folder", "")

                if not student_folder_name:
                    self.stdout.write(
                        self.style.WARNING(f"[SKIP] No student_folder specified for photos")
                    )
                    continue

                student_folder = dataset_path / student_folder_name

                if not student_folder.exists():
                    self.stdout.write(
                        self.style.ERROR(f"[ERROR] Student folder not found: {student_folder}")
                    )
                    continue

                # Get all image files from student folder
                image_extensions = {".jpg", ".jpeg", ".png", ".webp"}
                photo_files = sorted(
                    [f for f in student_folder.iterdir() if f.suffix.lower() in image_extensions]
                )

                if not photo_files:
                    self.stdout.write(
                        self.style.WARNING(f"[SKIP] No photos found in {student_folder}")
                    )
                    continue

                # Delete existing photos for this student
                StudentPhoto.objects.filter(student=student).delete()

                # Upload all photos (first = primary)
                for idx, photo_file in enumerate(photo_files):
                    is_primary = idx == 0  # First photo is primary

                    obj = StudentPhoto(
                        student=student, is_primary=is_primary, captured_at=timezone.now()
                    )
                    with open(photo_file, "rb") as f:
                        obj.photo.save(photo_file.name, File(f), save=True)

                    primary_label = " (PRIMARY)" if is_primary else ""
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"[OK] Photo {idx+1}/{len(photo_files)}: {obj.photo.name}{primary_label}"
                        )
                    )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Total photos for {student.encrypted_name}: {len(photo_files)}\n"
                    )
                )

        self.stdout.write(self.style.SUCCESS("\n=== Seed complete! ==="))
