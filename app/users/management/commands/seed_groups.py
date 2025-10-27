"""
Management command to seed Groups and Permissions.

Industry Standard (AWS IAM / Google Cloud IAM approach):
- Groups cannot be created via admin panel (enforced in admin.py)
- All groups/permissions defined in code (version controlled)
- Idempotent - safe to run multiple times
- Follows "deny by default, grant explicitly" principle

Usage:
    python manage.py seed_groups

This command is run during deployment after migrations.
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed Groups (Roles) and Permissions following IAM principles"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Seeding Groups and Permissions (IAM Model)"))
        self.stdout.write("=" * 60)

        # Define groups and their permissions
        # Format: {group_name: {app_label: {model: [permissions]}}}
        groups_config = {
            "Super Administrator": {
                "users": {"user": ["add", "change", "delete", "view"]},
                "students": {
                    "school": ["add", "change", "delete", "view"],
                    "student": ["add", "change", "delete", "view"],
                    "parent": ["add", "change", "delete", "view"],
                    "studentphoto": ["add", "change", "delete", "view"],
                },
                "buses": {
                    "bus": ["add", "change", "delete", "view"],
                    "route": ["add", "change", "delete", "view"],
                },
                "kiosks": {"kiosk": ["add", "change", "delete", "view"]},
                "events": {"boardingevent": ["add", "change", "delete", "view"]},
            },
            "Backend Engineer": {
                # Read-only access to all models
                "users": {"user": ["view"]},
                "students": {
                    "school": ["view"],
                    "student": ["view"],
                    "parent": ["view"],
                    "studentphoto": ["view"],
                },
                "buses": {"bus": ["view"], "route": ["view"]},
                "kiosks": {"kiosk": ["view"]},
                "events": {"boardingevent": ["view"]},
            },
            "School Administrator": {
                # Mostly view-only, limited edit access within own school
                "students": {
                    "student": ["view"],  # View students only
                    "parent": ["view"],  # View parents only
                    "studentphoto": ["view"],  # View photos only
                },
                "buses": {
                    "bus": ["view"],  # View buses
                    "route": ["view"],  # View routes
                },
                "kiosks": {"kiosk": ["view"]},  # View kiosks
                "events": {"boardingevent": ["view"]},  # View boarding events
            },
            "Parent": {
                # View own children only (scope enforced in views)
                "students": {"student": ["view"], "parent": ["view"]},
                "buses": {"bus": ["view"], "route": ["view"]},
                "events": {"boardingevent": ["view"]},
            },
        }

        # Create groups and assign permissions
        for group_name, apps_config in groups_config.items():
            group, created = Group.objects.get_or_create(name=group_name)
            action = "Created" if created else "Updated"

            # Clear existing permissions (idempotent)
            group.permissions.clear()

            perm_count = 0
            for app_label, models_config in apps_config.items():
                for model_name, permission_codes in models_config.items():
                    try:
                        content_type = ContentType.objects.get(app_label=app_label, model=model_name)

                        for perm_code in permission_codes:
                            permission_codename = f"{perm_code}_{model_name}"
                            permission = Permission.objects.get(codename=permission_codename, content_type=content_type)
                            group.permissions.add(permission)
                            perm_count += 1

                    except ContentType.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f"  WARNING: ContentType not found: {app_label}.{model_name} (skipping)"))
                    except Permission.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f"  WARNING: Permission not found: {perm_code}_{model_name} (skipping)"))

            self.stdout.write(self.style.SUCCESS(f"DONE: {action} '{group_name}' with {perm_count} permissions"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("Groups seeded successfully!"))
        self.stdout.write("")
        self.stdout.write("Summary:")
        for group in Group.objects.all():
            self.stdout.write(f"  - {group.name}: {group.permissions.count()} permissions")
