"""
Management command to clear all Django sessions.

This is useful when migrating user_id from CharField to UUID, as old sessions
will have string user_ids that cannot be converted to UUIDs.
"""

from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Clear all Django sessions"

    def handle(self, *args, **options):
        count = Session.objects.count()
        Session.objects.all().delete()

        self.stdout.write(self.style.SUCCESS(f"Successfully cleared {count} session(s)"))
