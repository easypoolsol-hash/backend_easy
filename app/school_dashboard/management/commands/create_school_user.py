"""Management command to create a school dashboard user."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    """Create a school dashboard user (non-superadmin)."""

    help = "Create a school user for accessing the dashboard"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--username",
            type=str,
            default="school",
            help="Username for the school user (default: school)",
        )
        parser.add_argument(
            "--password",
            type=str,
            default="school123",
            help="Password for the school user (default: school123)",
        )
        parser.add_argument(
            "--email",
            type=str,
            default="school@easypool.com",
            help="Email for the school user",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        username = options["username"]
        password = options["password"]
        email = options["email"]

        # Check if user already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f"User '{username}' already exists. Updating password..."))
            user = User.objects.get(username=username)
            user.set_password(password)
            user.email = email
            user.is_staff = True  # Allow admin login
            user.is_superuser = False  # NOT a superuser
            user.save()

            self.stdout.write(self.style.SUCCESS(f"✓ Updated user '{username}' with new password"))
        else:
            # Create new user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                is_staff=True,  # Allow admin/dashboard login
                is_superuser=False,  # NOT a superuser
            )

            self.stdout.write(self.style.SUCCESS(f"✓ Created school user '{username}'"))

        # Display credentials
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("SCHOOL DASHBOARD CREDENTIALS"))
        self.stdout.write("=" * 50)
        self.stdout.write(f"Username: {username}")
        self.stdout.write(f"Password: {password}")
        self.stdout.write(f"Email:    {email}")
        self.stdout.write("Role:     School Staff (NOT Superadmin)")
        self.stdout.write("=" * 50)
        self.stdout.write("\nLogin at: http://localhost:8000/admin/login/")
        self.stdout.write("Then visit: http://localhost:8000/school/\n")
