"""
Real-time BigQuery Streaming for Development/A/B Testing

Sends boarding events to BigQuery immediately after creation.
Enable with: BIGQUERY_STREAMING_ENABLED=True in settings.

For production: Use daily batch export (cost-effective)
For development: Use real-time streaming (fast feedback)
"""

import logging
from typing import Any

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="events.BoardingEvent")
def stream_to_bigquery(sender, instance, created, **kwargs):
    """
    Stream boarding event to BigQuery immediately after creation.

    Only runs if:
    - BIGQUERY_STREAMING_ENABLED=True in settings
    - Event was just created (not updated)
    - Event has backend verification data
    """
    # Check if streaming is enabled
    if not getattr(settings, "BIGQUERY_STREAMING_ENABLED", False):
        return

    # Only stream new events, not updates
    if not created:
        return

    # Only stream events with backend verification
    if not instance.backend_verified_at:
        return

    try:
        from google.cloud import bigquery  # type: ignore[attr-defined]

        # Get BigQuery config from settings
        project_id = getattr(settings, "BIGQUERY_PROJECT_ID", "easypool-backend")
        dataset_id = getattr(settings, "BIGQUERY_DATASET_ID", "ml_analytics")
        table_id = f"{project_id}.{dataset_id}.boarding_events"

        # Initialize BigQuery client
        client = bigquery.Client(project=project_id)

        # Format event for BigQuery
        row = _format_event_for_bigquery(instance)

        # Stream insert (real-time)
        errors = client.insert_rows_json(table_id, [row])

        if errors:
            logger.error(f"BigQuery streaming insert failed: {errors}")
        else:
            logger.info(f"Streamed event {instance.event_id} to BigQuery")

    except Exception as e:
        # Don't fail the request if BigQuery streaming fails
        logger.error(f"BigQuery streaming error: {e}", exc_info=True)


def _format_event_for_bigquery(event) -> dict[str, Any]:
    """Format BoardingEvent for BigQuery insertion"""

    # Parse model_consensus_data JSON
    consensus_data = event.model_consensus_data or {}

    # Extract model results
    model_results_raw = consensus_data.get("model_results", {})
    model_results_formatted = []

    for model_name, result in model_results_raw.items():
        # Format top-5 scores
        top_5_formatted = []
        if result.get("top_5_scores"):
            for student_id, score in result["top_5_scores"].items():
                top_5_formatted.append({"student_id": student_id, "score": float(score)})

        model_results_formatted.append(
            {
                "model_name": model_name,
                "predicted_student_id": result.get("student_id"),
                "confidence_score": float(result.get("confidence_score", 0.0)),
                "top_k_gap": float(result.get("top_k_gap", 0.0)),
                "is_ambiguous": result.get("is_ambiguous", False),
                "top_5_scores": top_5_formatted,
            }
        )

    # Detect if fast path was used (single model result = cascading fast path)
    used_fast_path = len(model_results_raw) == 1 and "mobilefacenet" in model_results_raw
    escalated_to_ensemble = len(model_results_raw) > 1

    return {
        "event_id": str(event.event_id),
        "timestamp": event.created_at.isoformat(),
        "kiosk_id": str(event.kiosk_id) if event.kiosk_id else None,
        "kiosk_name": None,  # Will be enriched from kiosk table if needed
        "student_id": str(event.student_id) if event.student_id else None,
        "student_name": None,  # Will be enriched from student table if needed
        "verification_status": consensus_data.get("verification_status"),
        "confidence_level": consensus_data.get("confidence_level"),
        "confidence_score": float(consensus_data.get("confidence_score", 0.0)) if consensus_data.get("confidence_score") else None,
        "consensus_count": consensus_data.get("consensus_count"),
        "config_version": event.backend_config_version,
        "model_results": model_results_formatted,
        "used_fast_path": used_fast_path,
        "escalated_to_ensemble": escalated_to_ensemble,
    }
