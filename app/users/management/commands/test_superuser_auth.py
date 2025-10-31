"""
Django management command to test superuser authentication.

Usage:
    python manage.py test_superuser_auth
"""

import os

from django.contrib.auth import authenticate, get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Test superuser authentication with environment variables"

    def handle(self, *args, **options):
        # Get credentials from environment variables (same as createsuperuser_secure)
        username = os.getenv("DJANGO_SUPERUSER_USERNAME")
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

        if not username or not password:
            self.stdout.write(self.style.ERROR("DJANGO_SUPERUSER_USERNAME and DJANGO_SUPERUSER_PASSWORD environment variables must be set"))
            return

        # Check if user exists
        try:
            user = User.objects.get(username=username)
            self.stdout.write(
                self.style.SUCCESS(f"Superuser found: {username} (staff: {user.is_staff}, superuser: {user.is_superuser}, active: {user.is_active})")
            )
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Superuser {username} does not exist"))
            return

        # Test authentication
        authenticated_user = authenticate(username=username, password=password)

        if authenticated_user:
            self.stdout.write(self.style.SUCCESS(f"Authentication successful for {username}"))
        else:
            self.stdout.write(self.style.ERROR(f"Authentication failed for {username} with provided password"))

            # Show password hash info (for debugging)
            self.stdout.write(f"Password hash starts with: {user.password[:20]}...")
            self.stdout.write("Password hash algorithm check:")
            if user.password.startswith("pbkdf2_sha256$"):
                self.stdout.write("  - Uses PBKDF2 SHA256 (Django default)")
            else:
                self.stdout.write(f"  - Uses: {user.password.split('$')[0] if '$' in user.password else 'unknown'}")
