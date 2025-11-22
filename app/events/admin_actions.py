"""
Django Admin Actions for Manual BigQuery Export

Adds "Export to BigQuery" button in Django Admin for instant analytics.
Perfect for development/testing - no waiting for scheduled exports!
"""

import logging

from django.contrib import admin, messages

logger = logging.getLogger(__name__)


@admin.action(description="Export selected events to BigQuery (instant)")
def export_selected_to_bigquery(modeladmin, request, queryset):
    """
    Export selected boarding events to BigQuery immediately.

    Usage:
    1. Go to Django Admin → Boarding Events
    2. Select events you want to analyze
    3. Actions dropdown → "Export to BigQuery (instant)"
    4. Click Go
    5. Check Looker Studio in 30 seconds!
    """
    try:
        from analytics.signals import _format_event_for_bigquery
        from google.cloud import bigquery  # type: ignore[attr-defined]

        # BigQuery config
        project_id = "easypool-backend"
        dataset_id = "ml_analytics"
        table_id = f"{project_id}.{dataset_id}.boarding_events"

        # Initialize BigQuery client
        client = bigquery.Client(project=project_id)

        # Format events for BigQuery
        rows_to_insert = []
        for event in queryset:
            if event.backend_verified_at:  # Only export verified events
                row = _format_event_for_bigquery(event)
                rows_to_insert.append(row)

        if not rows_to_insert:
            modeladmin.message_user(request, "No verified events to export", level=messages.WARNING)
            return

        # Insert to BigQuery
        errors = client.insert_rows_json(table_id, rows_to_insert)

        if errors:
            modeladmin.message_user(request, f"Export failed: {errors}", level=messages.ERROR)
        else:
            modeladmin.message_user(
                request,
                f"Successfully exported {len(rows_to_insert)} events to BigQuery! Check Looker Studio in 30 seconds.",
                level=messages.SUCCESS,
            )
            logger.info(f"Manually exported {len(rows_to_insert)} events to BigQuery")

    except Exception as e:
        modeladmin.message_user(request, f"Export error: {e}", level=messages.ERROR)
        logger.error(f"Manual BigQuery export failed: {e}", exc_info=True)


@admin.action(description="Export ALL events from last hour to BigQuery")
def export_last_hour_to_bigquery(modeladmin, request, queryset):
    """
    Export all events from the last hour to BigQuery.

    Useful during active development/testing.
    """
    from datetime import timedelta

    from django.utils import timezone

    from events.models import BoardingEvent

    # Get all events from last hour
    one_hour_ago = timezone.now() - timedelta(hours=1)
    recent_events = BoardingEvent.objects.filter(backend_verified_at__gte=one_hour_ago)

    # Use the export_selected action
    export_selected_to_bigquery(modeladmin, request, recent_events)
