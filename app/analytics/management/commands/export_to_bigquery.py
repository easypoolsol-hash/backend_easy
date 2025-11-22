"""
Export Boarding Events to BigQuery for ML Analytics

Separates analytics from backend - stores ML metrics in BigQuery for:
- Model performance tracking (FAR, FRR, accuracy per model)
- Top-K analysis (gap distributions, ambiguous cases)
- Drift detection (score distributions over time)
- Business metrics (boarding time, manual review rate)

Usage:
    python manage.py export_to_bigquery [--days=7] [--batch_size=1000]
"""

from datetime import timedelta
import logging
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone
from google.cloud import bigquery

from events.models import BoardingEvent

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Export boarding events to BigQuery for ML analytics (separate from backend)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=1,
            help="Number of days of data to export (default: 1 = yesterday's data)",
        )
        parser.add_argument(
            "--batch_size",
            type=int,
            default=1000,
            help="Batch size for BigQuery inserts (default: 1000)",
        )
        parser.add_argument(
            "--dataset",
            type=str,
            default="ml_analytics",
            help="BigQuery dataset name (default: ml_analytics)",
        )
        parser.add_argument(
            "--project",
            type=str,
            default="easypool-backend",
            help="GCP project ID (default: easypool-backend)",
        )

    def handle(self, *args, **options):
        days = options["days"]
        batch_size = options["batch_size"]
        dataset_id = options["dataset"]
        project_id = options["project"]

        self.stdout.write(self.style.SUCCESS("📊 Starting BigQuery export"))
        self.stdout.write(f"  Project: {project_id}")
        self.stdout.write(f"  Dataset: {dataset_id}")
        self.stdout.write(f"  Days: {days}")
        self.stdout.write(f"  Batch size: {batch_size}")

        # Initialize BigQuery client
        client = bigquery.Client(project=project_id)

        # Ensure dataset exists
        self._ensure_dataset(client, dataset_id)

        # Ensure tables exist
        self._ensure_tables(client, dataset_id)

        # Export data
        cutoff_date = timezone.now() - timedelta(days=days)
        events = BoardingEvent.objects.filter(created_at__gte=cutoff_date).select_related("kiosk", "student")

        total_events = events.count()
        self.stdout.write(f"\n✅ Found {total_events} events to export\n")

        if total_events == 0:
            self.stdout.write(self.style.WARNING("No events to export"))
            return

        # Process in batches
        exported_count = 0
        for i in range(0, total_events, batch_size):
            batch = events[i : i + batch_size]
            rows_to_insert = []

            for event in batch:
                row = self._format_event_for_bigquery(event)
                rows_to_insert.append(row)

            # Insert batch
            table_id = f"{project_id}.{dataset_id}.boarding_events"
            errors = client.insert_rows_json(table_id, rows_to_insert)

            if errors:
                self.stdout.write(self.style.ERROR(f"❌ Errors inserting batch {i // batch_size + 1}: {errors}"))
            else:
                exported_count += len(rows_to_insert)
                self.stdout.write(f"  ✅ Exported batch {i // batch_size + 1}: {len(rows_to_insert)} events")

        self.stdout.write(self.style.SUCCESS(f"\n🎉 Export complete: {exported_count}/{total_events} events exported"))

    def _ensure_dataset(self, client: bigquery.Client, dataset_id: str):
        """Create dataset if it doesn't exist"""
        dataset_ref = client.dataset(dataset_id)

        try:
            client.get_dataset(dataset_ref)
            logger.info(f"Dataset {dataset_id} already exists")
        except Exception:
            # Create dataset
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = "asia-south1"  # Match your region
            dataset.description = "ML analytics data - separate from backend database"
            client.create_dataset(dataset)
            logger.info(f"Created dataset {dataset_id}")

    def _ensure_tables(self, client: bigquery.Client, dataset_id: str):
        """Create BigQuery tables if they don't exist"""

        # Table 1: Boarding Events with ML metrics
        table_id = f"{client.project}.{dataset_id}.boarding_events"
        schema = [
            bigquery.SchemaField("event_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("kiosk_id", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("kiosk_name", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("student_id", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("student_name", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("verification_status", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("confidence_level", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("confidence_score", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("consensus_count", "INTEGER", mode="NULLABLE"),
            bigquery.SchemaField("config_version", "INTEGER", mode="NULLABLE"),
            # Model results (nested)
            bigquery.SchemaField(
                "model_results",
                "RECORD",
                mode="REPEATED",
                fields=[
                    bigquery.SchemaField("model_name", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("predicted_student_id", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("confidence_score", "FLOAT", mode="NULLABLE"),
                    bigquery.SchemaField("top_k_gap", "FLOAT", mode="NULLABLE"),
                    bigquery.SchemaField("is_ambiguous", "BOOLEAN", mode="NULLABLE"),
                    bigquery.SchemaField(
                        "top_5_scores",
                        "RECORD",
                        mode="REPEATED",
                        fields=[
                            bigquery.SchemaField("student_id", "STRING", mode="REQUIRED"),
                            bigquery.SchemaField("score", "FLOAT", mode="REQUIRED"),
                        ],
                    ),
                ],
            ),
            # Cascading info
            bigquery.SchemaField("used_fast_path", "BOOLEAN", mode="NULLABLE"),
            bigquery.SchemaField("escalated_to_ensemble", "BOOLEAN", mode="NULLABLE"),
        ]

        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="timestamp",
        )

        try:
            client.create_table(table)
            logger.info(f"Created table {table_id}")
        except Exception as e:
            if "Already Exists" in str(e):
                logger.info(f"Table {table_id} already exists")
            else:
                raise

    def _format_event_for_bigquery(self, event: BoardingEvent) -> dict[str, Any]:
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
            "kiosk_id": str(event.kiosk.kiosk_id) if event.kiosk else None,
            "kiosk_name": event.kiosk.kiosk_name if event.kiosk else None,
            "student_id": str(event.student.student_id) if event.student else None,
            "student_name": event.student.name if event.student else None,
            "verification_status": consensus_data.get("verification_status"),
            "confidence_level": consensus_data.get("confidence_level"),
            "confidence_score": float(consensus_data.get("confidence_score", 0.0)) if consensus_data.get("confidence_score") else None,
            "consensus_count": consensus_data.get("consensus_count"),
            "config_version": event.backend_config_version,
            "model_results": model_results_formatted,
            "used_fast_path": used_fast_path,
            "escalated_to_ensemble": escalated_to_ensemble,
        }
