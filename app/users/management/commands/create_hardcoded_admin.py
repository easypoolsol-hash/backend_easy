"""
Create hardcoded superuser - runs on every container startup (idempotent)
Fortune 500 pattern: Bootstrap admin for initial access
After first login, create proper SSO admin and delete this account
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import OperationalError

User = get_user_model()

# HARDCODED CREDENTIALS - Change after first login
ADMIN_USERNAME = "admin123"
ADMIN_EMAIL = "admin@easypool.internal"
ADMIN_PASSWORD = "EasyPool2025Admin"  # Change immediately after first login


class Command(BaseCommand):
    help = "Create/update hardcoded superuser (idempotent)"

    def handle(self, *args, **options):
        try:
            # Check if database table exists
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM auth_user LIMIT 1")
        except OperationalError:
            self.stdout.write("[SKIP] Database not ready, migrations not applied yet")
            return

        try:
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

            action = "Created" if created else "Updated"
            self.stdout.write(f"[SUCCESS] {action} hardcoded admin: {ADMIN_USERNAME}")

        except Exception as e:
            self.stdout.write(f"[ERROR] Failed to create admin: {e}")
