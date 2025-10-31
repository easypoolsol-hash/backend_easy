"""
ATOMIC BOOTSTRAP ADMIN - Singleton Pattern
Runs once, creates admin, never fails
"""

import time

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.db.utils import OperationalError

User = get_user_model()

ADMIN_USERNAME = "admin123"
ADMIN_EMAIL = "admin@easypool.internal"
ADMIN_PASSWORD = "EasyPool2025Admin"


class Command(BaseCommand):
    help = "Ensure bootstrap admin exists (atomic, idempotent, never fails)"

    def wait_for_db(self, max_retries=30):
        """Wait for database to be ready"""
        for i in range(max_retries):
            try:
                connection.ensure_connection()
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                return True
            except OperationalError:
                if i == max_retries - 1:
                    raise
                time.sleep(1)
        return False

    def table_exists(self, table_name):
        """Check if table exists"""
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT 1 FROM {table_name} LIMIT 1")
            return True
        except OperationalError:
            return False

    def handle(self, *args, **options):
        self.stdout.write("[BOOTSTRAP] Starting admin creation...")

        # Step 1: Wait for database
        try:
            self.wait_for_db()
            self.stdout.write("[BOOTSTRAP] Database connected")
        except Exception as e:
            self.stdout.write(f"[BOOTSTRAP] Database not ready: {e}")
            return

        # Step 2: Check if migrations ran
        if not self.table_exists("auth_user"):
            self.stdout.write("[BOOTSTRAP] Migrations not applied yet, skipping")
            return

        # Step 3: Create admin atomically
        try:
            with transaction.atomic():
                user, created = User.objects.update_or_create(
                    username=ADMIN_USERNAME,
                    defaults={
                        "email": ADMIN_EMAIL,
                        "is_staff": True,
                        "is_superuser": True,
                        "is_active": True,
                    },
                )
                user.set_password(ADMIN_PASSWORD)
                user.save()

            action = "CREATED" if created else "VERIFIED"
            self.stdout.write(f"[BOOTSTRAP] {action} admin: {ADMIN_USERNAME}")
            self.stdout.write("[BOOTSTRAP] Login URL: /admin/")
            self.stdout.write(f"[BOOTSTRAP] Username: {ADMIN_USERNAME}")
            self.stdout.write(f"[BOOTSTRAP] Password: {ADMIN_PASSWORD}")
            self.stdout.write("[BOOTSTRAP] SUCCESS - Admin ready")

        except Exception as e:
            self.stdout.write(f"[BOOTSTRAP] FAILED: {e}")
            raise  # Fail loudly so we see it in logs
