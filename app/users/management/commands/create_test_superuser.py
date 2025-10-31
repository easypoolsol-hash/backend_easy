"""
Django management command to create a test superuser with known credentials.

SECURITY WARNING: This command creates a superuser with hardcoded credentials.
Only use this for testing purposes in development/staging environments.
Never use in production!

Usage:
    python manage.py create_test_superuser
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from users.models import User


class Command(BaseCommand):
    help = "Create a test superuser with known credentials (DEVELOPMENT ONLY)"

    def handle(self, *args, **options):
        # Hardcoded test credentials - NEVER USE IN PRODUCTION
        test_username = "testadmin"
        test_email = "testadmin@easypool.com"
        test_password = "testpass123"

        self.stdout.write(self.style.WARNING("⚠️  SECURITY WARNING: Creating test superuser with known credentials!"))
        self.stdout.write(self.style.WARNING("This should NEVER be used in production environments!"))

        # Check if test superuser already exists
        try:
            existing_user = User.objects.get(username=test_username)
            self.stdout.write(self.style.WARNING(f"Test superuser '{test_username}' already exists. Deleting and recreating..."))
            existing_user.delete()
        except User.DoesNotExist:
            pass

        # Create test superuser atomically
        try:
            with transaction.atomic():
                user = User.objects.create_superuser(
                    username=test_username,
                    email=test_email,
                    password=test_password,
                )

                self.stdout.write(self.style.SUCCESS(f"Test superuser created successfully: {test_username}"))
                self.stdout.write(f"Email: {test_email}")
                self.stdout.write(f"Password: {test_password}")
                self.stdout.write(f"Is staff: {user.is_staff}")
                self.stdout.write(f"Is superuser: {user.is_superuser}")
                self.stdout.write(f"Is active: {user.is_active}")

                self.stdout.write(self.style.WARNING("🔐 REMEMBER: Delete this test user after testing!"))
                self.stdout.write(self.style.WARNING("🔄 Change password immediately in production!"))

        except Exception as e:
            raise CommandError(f"Failed to create test superuser: {e!r}") from e
