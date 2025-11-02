"""
Flush database - Drop all tables for fresh migration (dev only)
Fortune 500 pattern: Controlled database reset for development
WARNING: This will destroy ALL data in the database
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Drop all tables in database (dev only - for fresh migrations)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force execution without confirmation",
        )

    def handle(self, *args, **options):
        # Safety check: Only allow in LOCAL/CI/DEV environments
        env = getattr(settings, "DJANGO_ENV", "LOCAL")
        if env not in ["LOCAL", "CI", "dev"]:
            self.stdout.write(self.style.ERROR(f"[BLOCKED] Cannot flush database in {env} environment. Only allowed in LOCAL/CI/dev."))
            return

        # Confirmation check
        if not options["force"]:
            self.stdout.write(self.style.WARNING("\n⚠️  WARNING: This will DROP ALL TABLES in the database!"))
            self.stdout.write(self.style.WARNING("All data will be PERMANENTLY LOST."))
            confirm = input("\nType 'yes' to continue: ")
            if confirm.lower() != "yes":
                self.stdout.write(self.style.ERROR("[CANCELLED] Database flush aborted."))
                return

        try:
            with connection.cursor() as cursor:
                # Get all table names
                cursor.execute(
                    """
                    SELECT tablename FROM pg_tables
                    WHERE schemaname = 'public'
                """
                )
                tables = cursor.fetchall()

                if not tables:
                    self.stdout.write(self.style.WARNING("[INFO] No tables found in database."))
                    return

                # Disable foreign key checks
                cursor.execute("SET CONSTRAINTS ALL DEFERRED;")

                # Drop all tables
                table_count = 0
                for (table_name,) in tables:
                    cursor.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE;')
                    table_count += 1
                    self.stdout.write(f"[DROPPED] Table: {table_name}")

                # Re-enable foreign key checks
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE;")

                self.stdout.write(
                    self.style.SUCCESS(f"\n[SUCCESS] Dropped {table_count} tables. Database is clean. Run 'migrate' to recreate schema.")
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[ERROR] Failed to flush database: {e}"))
