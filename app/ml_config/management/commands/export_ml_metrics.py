"""
Export ML Performance Metrics to Google Cloud Monitoring

Run this command periodically (via Cloud Scheduler or Celery Beat) to export
ML model performance metrics to Cloud Monitoring for dashboards and alerting.

Usage:
    python manage.py export_ml_metrics
    python manage.py export_ml_metrics --dry-run
    python manage.py export_ml_metrics --time-window=hourly
"""

from datetime import timedelta
import logging

from django.core.management.base import BaseCommand
from django.db.models import F, Q
from django.utils import timezone
from google.cloud import monitoring_v3  # type: ignore[attr-defined]

from events.models import BoardingEvent
from ml_config.models import BackendModelConfiguration

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Export ML performance metrics to Google Cloud Monitoring"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print metrics without sending to Cloud Monitoring",
        )
        parser.add_argument(
            "--time-window",
            type=str,
            default="hourly",
            choices=["hourly", "daily"],
            help="Time window for metrics calculation (default: hourly)",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        time_window = options.get("time_window", "hourly")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No metrics will be sent"))

        try:
            # Initialize Cloud Monitoring client
            client = monitoring_v3.MetricServiceClient()
            project_name = f"projects/{client.project_path.split('/')[1]}"

            # Calculate time window
            now = timezone.now()
            if time_window == "hourly":
                start_time = now - timedelta(hours=1)
            else:  # daily
                start_time = now - timedelta(days=1)

            metrics_sent = 0

            # 1. Export verification accuracy per model
            metrics_sent += self._export_verification_accuracy(client, project_name, start_time, dry_run)

            # 2. Export kiosk-backend mismatch rate
            metrics_sent += self._export_mismatch_rate(client, project_name, start_time, time_window, dry_run)

            # 3. Export consensus confidence scores
            metrics_sent += self._export_confidence_scores(client, project_name, start_time, dry_run)

            self.stdout.write(self.style.SUCCESS(f"✓ Exported {metrics_sent} ML performance metrics (time window: {time_window})"))

        except Exception as e:
            logger.error(f"Failed to export ML metrics: {e}", exc_info=True)
            self.stdout.write(self.style.ERROR(f"✗ Failed to export metrics: {e}"))
            raise

    def _export_verification_accuracy(self, client, project_name, start_time, dry_run=False):
        """Export verification accuracy per model from consensus data"""
        metrics_sent = 0

        # Get recent boarding events with backend verification
        events = BoardingEvent.objects.filter(
            backend_verified_at__gte=start_time,
            backend_verification_status__in=["VERIFIED", "REJECTED"],
            model_consensus_data__isnull=False,
        )

        if not events.exists():
            self.stdout.write(self.style.WARNING("  No verified events in time window"))
            return 0

        # Calculate accuracy per model from consensus data
        model_stats = {
            "mobilefacenet": {"correct": 0, "total": 0},
            "arcface_int8": {"correct": 0, "total": 0},
            "adaface": {"correct": 0, "total": 0},
        }

        for event in events:
            consensus_data = event.model_consensus_data
            if not consensus_data or "model_results" not in consensus_data:
                continue

            # Get backend prediction (what the consensus system verified)
            backend_prediction = event.backend_student_id

            # Check each model's prediction
            for model_result in consensus_data.get("model_results", []):
                model_name = model_result.get("model_name")
                predicted_id = model_result.get("predicted_student_id")

                if model_name in model_stats:
                    model_stats[model_name]["total"] += 1
                    # A model is "correct" if it predicted the student that backend verified
                    if predicted_id == backend_prediction:
                        model_stats[model_name]["correct"] += 1

        # Get active config version
        active_config = BackendModelConfiguration.get_active_config()
        config_version = f"v{active_config.version}"

        # Export accuracy for each model
        for model_name, stats in model_stats.items():
            if stats["total"] > 0:
                accuracy = (stats["correct"] / stats["total"]) * 100.0

                self._write_metric(
                    client,
                    project_name,
                    "custom.googleapis.com/ml/verification_accuracy",
                    accuracy,
                    {
                        "model_name": model_name,
                        "config_version": config_version,
                    },
                    dry_run,
                )
                metrics_sent += 1

                if dry_run or self.verbosity >= 1:
                    self.stdout.write(f"  {model_name}: {accuracy:.2f}% ({stats['correct']}/{stats['total']})")

        return metrics_sent

    def _export_mismatch_rate(self, client, project_name, start_time, time_window, dry_run=False):
        """Export mismatch rate between kiosk and backend predictions"""
        # Get events with both kiosk and backend predictions
        events = BoardingEvent.objects.filter(
            backend_verified_at__gte=start_time,
            student_id__isnull=False,  # Kiosk prediction exists
            backend_student_id__isnull=False,  # Backend prediction exists
        )

        total_events = events.count()
        if total_events == 0:
            self.stdout.write(self.style.WARNING("  No events with both predictions in time window"))
            return 0

        # Count mismatches (where kiosk prediction != backend prediction)
        mismatches = events.filter(~Q(student_id=F("backend_student_id"))).count()

        mismatch_rate = (mismatches / total_events) * 100.0

        self._write_metric(
            client,
            project_name,
            "custom.googleapis.com/ml/mismatch_rate",
            mismatch_rate,
            {
                "time_window": time_window,
            },
            dry_run,
        )

        if dry_run or self.verbosity >= 1:
            self.stdout.write(f"  Mismatch Rate ({time_window}): {mismatch_rate:.2f}% ({mismatches}/{total_events})")

        return 1

    def _export_confidence_scores(self, client, project_name, start_time, dry_run=False):
        """Export average consensus confidence scores by level"""
        metrics_sent = 0

        # Get verified events
        events = BoardingEvent.objects.filter(
            backend_verified_at__gte=start_time,
            backend_verification_confidence__isnull=False,
        )

        if not events.exists():
            self.stdout.write(self.style.WARNING("  No events with confidence scores in time window"))
            return 0

        # Calculate average confidence per level
        confidence_levels = ["HIGH", "MEDIUM", "LOW"]

        for level in confidence_levels:
            level_events = events.filter(backend_verification_confidence=level)
            count = level_events.count()

            if count > 0:
                # Get average combined score from consensus data
                avg_score = 0.0
                score_count = 0

                for event in level_events:
                    consensus_data = event.model_consensus_data
                    if consensus_data and "combined_score" in consensus_data:
                        avg_score += consensus_data["combined_score"]
                        score_count += 1

                if score_count > 0:
                    avg_score = avg_score / score_count

                    self._write_metric(
                        client,
                        project_name,
                        "custom.googleapis.com/ml/consensus_confidence",
                        avg_score,
                        {
                            "confidence_level": level.lower(),
                        },
                        dry_run,
                    )
                    metrics_sent += 1

                    if dry_run or self.verbosity >= 1:
                        self.stdout.write(f"  Avg Confidence ({level}): {avg_score:.4f} ({count} events)")

        return metrics_sent

    def _write_metric(self, client, project_name, metric_type, value, labels, dry_run=False):
        """Write a single metric point to Cloud Monitoring"""
        if dry_run:
            self.stdout.write(f"  [DRY RUN] {metric_type} = {value} {labels}")
            return

        series = monitoring_v3.TimeSeries()
        series.metric.type = metric_type
        series.resource.type = "generic_node"
        series.resource.labels["project_id"] = project_name.split("/")[1]
        series.resource.labels["location"] = "global"
        series.resource.labels["namespace"] = "ml_performance"
        series.resource.labels["node_id"] = "backend"

        # Add custom labels
        for key, val in labels.items():
            series.metric.labels[key] = str(val)

        # Add data point
        now = timezone.now()
        interval = monitoring_v3.TimeInterval({"end_time": {"seconds": int(now.timestamp())}})
        point = monitoring_v3.Point(
            {
                "interval": interval,
                "value": {"double_value": float(value)},
            }
        )
        series.points = [point]

        # Write to Cloud Monitoring
        client.create_time_series(name=project_name, time_series=[series])
