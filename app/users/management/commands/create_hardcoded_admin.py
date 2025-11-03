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
ADMIN_USERNAME = "admin"
ADMIN_EMAIL = "admin@easypool.internal"
ADMIN_PASSWORD = "admin"  # Change immediately after first login


class Command(BaseCommand):
    help = "Create/update hardcoded superuser (idempotent)"

    def handle(self, *args, **options):
        # Singleton pattern: Check if ALL migrations are applied (all-or-nothing)
        try:
            # Use Django's migration state - proper way to check if migrations complete
            from django.db.migrations.executor import MigrationExecutor

            executor = MigrationExecutor(connection)

            # Check if there are any unapplied migrations
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            if plan:
                self.stdout.write("[SKIP] Migrations not fully applied. Run migrate first.")
                return

            # Additional check: Try to query User model (works with custom user models)
            User.objects.exists()
        except (OperationalError, Exception) as e:
            self.stdout.write(f"[SKIP] Database not ready: {e}")
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
