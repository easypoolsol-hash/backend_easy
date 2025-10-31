"""
Django management command to create/update a hardcoded admin superuser.

SECURITY WARNING: This command creates a superuser with hardcoded credentials.
Only use this for testing purposes in development/staging environments.
Never use in production!

This command will:
- Create a superuser with username 'admin' and password 'admin123'
- If the user already exists, it will update the password to 'admin123'
- Email will be set to 'admin@easypool.com'

Usage:
    python manage.py create_hardcoded_admin
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from users.models import User


class Command(BaseCommand):
    help = "Create/update hardcoded admin superuser (DEVELOPMENT ONLY)"

    def handle(self, *args, **options):
        # Hardcoded credentials - NEVER USE IN PRODUCTION
        username = "admin"
        email = "admin@easypool.com"
        password = "admin123"

        self.stdout.write(self.style.WARNING("⚠️  SECURITY WARNING: Creating/updating hardcoded admin superuser!"))
        self.stdout.write(self.style.WARNING("This should NEVER be used in production environments!"))
        self.stdout.write(f"Username: {username}")
        self.stdout.write(f"Password: {password}")

        # Check if admin already exists
        try:
            existing_user = User.objects.get(username=username)
            self.stdout.write(self.style.WARNING(f"Admin user '{username}' already exists. Updating password..."))
            user = existing_user
        except User.DoesNotExist:
            user = None

        # Create or update admin superuser atomically
        try:
            with transaction.atomic():
                if user:
                    # Update existing admin
                    user.email = email
                    user.set_password(password)
                    user.is_staff = True
                    user.is_superuser = True
                    user.is_active = True
                    user.save()

                    # Ensure super admin group
                    try:
                        from django.contrib.auth.models import Group

                        super_admin_group, _ = Group.objects.get_or_create(name="Super Administrator")
                        user.groups.add(super_admin_group)
                    except Exception:
                        pass

                    self.stdout.write(self.style.SUCCESS(f"Admin user updated successfully: {username}"))
                else:
                    # Create new admin superuser
                    user = User.objects.create_superuser(
                        username=username,
                        email=email,
                        password=password,
                    )
                    self.stdout.write(self.style.SUCCESS(f"Admin superuser created successfully: {username}"))

                self.stdout.write(f"Email: {email}")
                self.stdout.write(f"Is staff: {user.is_staff}")
                self.stdout.write(f"Is superuser: {user.is_superuser}")
                self.stdout.write(f"Is active: {user.is_active}")

                self.stdout.write(self.style.WARNING("🔐 REMEMBER: Change password immediately after testing!"))
                self.stdout.write(self.style.WARNING("🔄 Never deploy this to production!"))

        except Exception as e:
            raise CommandError(f"Failed to create/update admin superuser: {e!r}") from e
