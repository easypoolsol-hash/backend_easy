"""
Management command to create a superuser programmatically.
Useful for production deployments where interactive input is not possible.

SECURITY CONSIDERATIONS:
- Only create superusers when absolutely necessary
- Use strong, unique passwords (generate with password manager)
- Enable 2FA immediately after creation
- Monitor superuser activity via audit logs
- Consider using service accounts for automation instead
- Rotate superuser credentials regularly

Usage:
    python manage.py createsuperuser_noninteractive \\
        --username admin --email admin@example.com --password mypassword
    # Or using environment variables:
    DJANGO_SUPERUSER_USERNAME=admin \\
    DJANGO_SUPERUSER_EMAIL=admin@example.com \\
    DJANGO_SUPERUSER_PASSWORD=mypassword \\
    python manage.py createsuperuser_noninteractive

Fortune 500 Alternative:
    - Use enterprise identity providers (Okta, Azure AD, Ping Identity)
    - Service accounts for automation
    - Manual provisioning through IT service desk
    - No auto-creation during deployment
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create a superuser programmatically (non-interactive)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            type=str,
            help="Username for the superuser",
        )
        parser.add_argument(
            "--email",
            type=str,
            help="Email for the superuser",
        )
        parser.add_argument(
            "--password",
            type=str,
            help="Password for the superuser",
        )
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Use environment variables or skip if user exists",
        )

    def handle(self, *args, **options):
        User = get_user_model()

        # Get credentials from command line args or environment variables
        username = options.get("username") or os.getenv("DJANGO_SUPERUSER_USERNAME")
        email = options.get("email") or os.getenv("DJANGO_SUPERUSER_EMAIL")
        password = options.get("password") or os.getenv("DJANGO_SUPERUSER_PASSWORD")

        # Validate required fields
        if not username:
            raise CommandError("Username is required. Provide --username or set DJANGO_SUPERUSER_USERNAME")
        if not password:
            raise CommandError("Password is required. Provide --password or set DJANGO_SUPERUSER_PASSWORD")

        # Check if user already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.warning(f"Superuser '{username}' already exists. Skipping creation."))
            return

        # Create the superuser
        try:
            User.objects.create_superuser(username=username, email=email, password=password)

            # Log the creation for audit purposes
            self.stdout.write(self.style.success(f"Superuser '{username}' created successfully!"))
            self.stdout.write(self.style.warning("⚠️  SECURITY REMINDER: Change password immediately and enable 2FA!"))

        except Exception as e:
            raise CommandError(f"Failed to create superuser: {e}") from e
