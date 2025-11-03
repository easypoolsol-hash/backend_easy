"""
Management command to create a superuser (Django standard pattern).

This command provides both interactive and non-interactive modes for creating
superusers with proper group assignment.

Usage:
    Interactive mode:
        python manage.py createsuperuser

    Non-interactive mode (for automation):
        python manage.py createsuperuser --username admin --email admin@example.com --password SecurePass123

Industry Standard:
- Superusers automatically assigned to "Super Administrator" group
- Follows Django's createsuperuser conventions
- Supports both interactive and automated workflows
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = "Create a superuser with Super Administrator group assignment"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            type=str,
            help="Username for the superuser",
        )
        parser.add_argument(
            "--email",
            type=str,
            help="Email address for the superuser",
        )
        parser.add_argument(
            "--password",
            type=str,
            help="Password for the superuser (non-interactive mode only)",
        )
        parser.add_argument(
            "--first-name",
            type=str,
            default="",
            help="First name (optional)",
        )
        parser.add_argument(
            "--last-name",
            type=str,
            default="",
            help="Last name (optional)",
        )
        parser.add_argument(
            "--noinput",
            action="store_true",
            help="Non-interactive mode (requires --username, --email, --password)",
        )

    def handle(self, *args, **options):
        username = options.get("username")
        email = options.get("email")
        password = options.get("password")
        first_name = options.get("first_name", "")
        last_name = options.get("last_name", "")
        noinput = options.get("noinput", False)

        # Non-interactive mode validation
        if noinput:
            if not username or not email or not password:
                raise CommandError("Non-interactive mode requires --username, --email, and --password")
        else:
            # Interactive mode
            self.stdout.write(self.style.SUCCESS("Create Superuser"))
            self.stdout.write("=" * 60)

            if not username:
                username = input("Username: ").strip()
                while not username:
                    self.stdout.write(self.style.ERROR("Username cannot be empty"))
                    username = input("Username: ").strip()

            if not email:
                email = input("Email: ").strip()
                while not email:
                    self.stdout.write(self.style.ERROR("Email cannot be empty"))
                    email = input("Email: ").strip()

            if not first_name:
                first_name = input("First name (optional): ").strip()

            if not last_name:
                last_name = input("Last name (optional): ").strip()

            if not password:
                from getpass import getpass

                password = getpass("Password: ")
                password_confirm = getpass("Password (again): ")

                while password != password_confirm:
                    self.stdout.write(self.style.ERROR("Passwords do not match"))
                    password = getpass("Password: ")
                    password_confirm = getpass("Password (again): ")

        # Validate username and email uniqueness
        if User.objects.filter(username=username).exists():
            raise CommandError(f"User with username '{username}' already exists")

        if User.objects.filter(email=email).exists():
            raise CommandError(f"User with email '{email}' already exists")

        # Create superuser within transaction
        try:
            with transaction.atomic():
                # Create the superuser
                user = User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                )

                # Ensure Super Administrator group exists and is assigned
                super_admin_group, group_created = Group.objects.get_or_create(name="Super Administrator")

                if group_created:
                    self.stdout.write(self.style.WARNING("Created 'Super Administrator' group (run seed_groups to configure permissions)"))

                # Add user to Super Administrator group (if not already added by UserManager)
                if not user.groups.filter(name="Super Administrator").exists():
                    user.groups.add(super_admin_group)

                self.stdout.write("")
                self.stdout.write(self.style.SUCCESS("=" * 60))
                self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' created successfully!"))
                self.stdout.write("")
                self.stdout.write("Details:")
                self.stdout.write(f"  Username: {user.username}")
                self.stdout.write(f"  Email: {user.email}")
                self.stdout.write(f"  Name: {user.get_full_name() or '(not set)'}")
                self.stdout.write(f"  Groups: {', '.join([g.name for g in user.groups.all()])}")
                self.stdout.write(f"  Superuser: {user.is_superuser}")
                self.stdout.write(f"  Staff: {user.is_staff}")
                self.stdout.write("")
                self.stdout.write(self.style.WARNING("Remember to run 'python manage.py seed_groups' to ensure permissions are configured"))

        except Exception as e:
            raise CommandError(f"Failed to create superuser: {e}") from e
