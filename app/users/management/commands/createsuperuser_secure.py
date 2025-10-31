"""
Django management command to create superuser securely.

SECURITY CONSIDERATIONS:
- Only create superusers when absolutely necessary
- Use strong, unique passwords (generate with password manager)
- Enable 2FA immediately after creation
- Monitor superuser activity via audit logs
- Consider using service accounts for automation instead
- Rotate superuser credentials regularly

Usage:
    python manage.py createsuperuser_secure --username admin --email admin@example.com
    # Or using environment variables:
    DJANGO_SUPERUSER_USERNAME=admin \\
    DJANGO_SUPERUSER_EMAIL=admin@example.com \\
    DJANGO_SUPERUSER_PASSWORD=securepassword \\
    python manage.py createsuperuser_secure --no-input

Fortune 500 Alternative:
    - Use enterprise identity providers (Okta, Azure AD, Ping Identity)
    - Service accounts for automation
    - Manual provisioning through IT service desk
    - No auto-creation during deployment
"""

import getpass
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = "Create a superuser securely with environment variables or prompts"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            type=str,
            help="Superuser username",
        )
        parser.add_argument(
            "--email",
            type=str,
            help="Superuser email address",
        )
        parser.add_argument(
            "--password",
            type=str,
            help="Superuser password (not recommended for production)",
        )
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Do not prompt for input, use environment variables",
        )

    def handle(self, *args, **options):
        # Check if superuser already exists
        try:
            user = User.objects.get(username=options.get("username") or os.getenv("DJANGO_SUPERUSER_USERNAME"))
            self.stdout.write(self.style.WARNING(f"Superuser {user.username} already exists. Updating password..."))
        except User.DoesNotExist:
            user = None

        # Get credentials from environment variables or prompts
        if options["no_input"]:
            username = os.getenv("DJANGO_SUPERUSER_USERNAME")
            email = os.getenv("DJANGO_SUPERUSER_EMAIL")
            password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

            if not username or not email or not password:
                raise CommandError(
                    "DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL and "
                    "DJANGO_SUPERUSER_PASSWORD environment variables must be set when using --no-input"
                )
        else:
            username = options.get("username")
            if not username:
                username = input("Username: ").strip()

            email = options.get("email")
            if not email:
                email = input("Email address: ").strip()

            password = options.get("password")
            if not password:
                password = getpass.getpass("Password: ")
                password_confirm = getpass.getpass("Password (again): ")

                if password != password_confirm:
                    raise CommandError("Passwords don't match")

        # Validate username
        if not username:
            raise CommandError("Username is required")

        # Validate email format
        if "@" not in email:
            raise CommandError("Invalid email address")

        # Validate password strength
        if len(password) < 8:
            raise CommandError("Password must be at least 8 characters long")

        # Create or update superuser atomically
        try:
            with transaction.atomic():
                if user:
                    # Update existing superuser
                    user.email = email
                    user.set_password(password)
                    user.save()
                    self.stdout.write(self.style.SUCCESS(f"Superuser password updated successfully: {username} ({email})"))
                else:
                    # Create new superuser
                    User.objects.create_superuser(
                        username=username,
                        email=email,
                        password=password,
                    )
                    self.stdout.write(self.style.SUCCESS(f"Superuser created successfully: {username} ({email})"))

                # Security reminder
                self.stdout.write(self.style.WARNING("⚠️  SECURITY REMINDER: Change password immediately and enable 2FA!"))

        except Exception as e:
            raise CommandError(f"Failed to create/update superuser: {e!r}") from e
