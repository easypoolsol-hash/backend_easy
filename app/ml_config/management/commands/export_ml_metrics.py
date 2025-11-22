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
import os

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
            project_id = os.environ.get("GCP_PROJECT_ID", "easypool-backend")
            project_name = f"projects/{project_id}"

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

            # 4. Export FAR/FRR (banking-grade metrics)
            metrics_sent += self._export_far_frr(client, project_name, start_time, dry_run)

            # 5. Export top-K gap analysis
            metrics_sent += self._export_top_k_gap(client, project_name, start_time, dry_run)

            # 6. Export cascading performance
            metrics_sent += self._export_cascading_stats(client, project_name, start_time, dry_run)

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

    def _export_far_frr(self, client, project_name, start_time, dry_run=False):
        """
        Export FAR/FRR (banking-grade metrics)

        FAR (False Accept Rate): Incorrectly verified events / Total verified events
        FRR (False Rejection Rate): Incorrectly rejected events / Total events

        Banking standards: FAR < 0.1%, FRR < 1%
        """
        metrics_sent = 0

        # Get all events with backend verification
        events = BoardingEvent.objects.filter(backend_verified_at__gte=start_time)
        total_events = events.count()

        if total_events == 0:
            return 0

        # FAR: False accepts (verified but wrong student)
        # For now, use mismatch between kiosk and backend as proxy
        verified_events = events.filter(backend_verification_status="VERIFIED", student_id__isnull=False, backend_student_id__isnull=False)
        verified_count = verified_events.count()

        if verified_count > 0:
            false_accepts = verified_events.filter(~Q(student_id=F("backend_student_id"))).count()
            far = (false_accepts / verified_count) * 100.0

            self._write_metric(client, project_name, "custom.googleapis.com/ml/far_daily", far, {"unit": "percent", "target": "0.1"}, dry_run)
            metrics_sent += 1

            if dry_run or self.verbosity >= 1:
                status = "✓" if far < 0.1 else "⚠️"
                self.stdout.write(f"  {status} FAR: {far:.3f}% ({false_accepts}/{verified_count}) [Banking target: <0.1%]")

        # FRR: False rejects (flagged/failed but should be verified)
        flagged_or_failed = events.filter(backend_verification_status__in=["FLAGGED", "REJECTED"]).count()
        if total_events > 0:
            frr = (flagged_or_failed / total_events) * 100.0

            self._write_metric(client, project_name, "custom.googleapis.com/ml/frr_daily", frr, {"unit": "percent", "target": "1.0"}, dry_run)
            metrics_sent += 1

            if dry_run or self.verbosity >= 1:
                status = "✓" if frr < 1.0 else "⚠️"
                self.stdout.write(f"  {status} FRR: {frr:.3f}% ({flagged_or_failed}/{total_events}) [Banking target: <1%]")

        return metrics_sent

    def _export_top_k_gap(self, client, project_name, start_time, dry_run=False):
        """
        Export average top-K gap (difference between #1 and #2 matches)

        Banking standard: Gap < 0.12 indicates ambiguous case (Lalit vs ADVIK)
        """
        events = BoardingEvent.objects.filter(backend_verified_at__gte=start_time, model_consensus_data__isnull=False)

        if not events.exists():
            return 0

        # Calculate average gap per model
        model_gaps = {"mobilefacenet": [], "arcface_int8": [], "adaface": []}

        for event in events:
            consensus_data = event.model_consensus_data
            if not consensus_data or "model_results" not in consensus_data:
                continue

            model_results = consensus_data.get("model_results", {})
            for model_name, result in model_results.items():
                if model_name in model_gaps and "top_k_gap" in result:
                    gap = result["top_k_gap"]
                    if gap > 0:  # Valid gap
                        model_gaps[model_name].append(gap)

        metrics_sent = 0
        for model_name, gaps in model_gaps.items():
            if gaps:
                avg_gap = sum(gaps) / len(gaps)
                ambiguous_count = sum(1 for g in gaps if g < 0.12)
                ambiguous_percent = (ambiguous_count / len(gaps)) * 100.0

                self._write_metric(client, project_name, "custom.googleapis.com/ml/top_k_gap_avg", avg_gap, {"model_name": model_name}, dry_run)

                self._write_metric(
                    client,
                    project_name,
                    "custom.googleapis.com/ml/ambiguous_case_rate",
                    ambiguous_percent,
                    {"model_name": model_name},
                    dry_run,
                )

                metrics_sent += 2

                if dry_run or self.verbosity >= 1:
                    self.stdout.write(f"  {model_name}: Avg gap={avg_gap:.3f}, Ambiguous={ambiguous_percent:.1f}% ({ambiguous_count}/{len(gaps)})")

        return metrics_sent

    def _export_cascading_stats(self, client, project_name, start_time, dry_run=False):
        """
        Export cascading performance (fast path vs ensemble)

        Expected: 80% fast path (MobileFaceNet alone), 20% escalated to ensemble
        """
        events = BoardingEvent.objects.filter(backend_verified_at__gte=start_time, model_consensus_data__isnull=False)
        total_events = events.count()

        if total_events == 0:
            return 0

        # Detect fast path: Only mobilefacenet in model_results
        fast_path_count = 0
        ensemble_count = 0

        for event in events:
            consensus_data = event.model_consensus_data
            if not consensus_data or "model_results" not in consensus_data:
                continue

            model_results = consensus_data.get("model_results", {})
            num_models = len(model_results)

            if num_models == 1 and "mobilefacenet" in model_results:
                fast_path_count += 1
            elif num_models > 1:
                ensemble_count += 1

        if total_events > 0:
            fast_path_percent = (fast_path_count / total_events) * 100.0
            ensemble_percent = (ensemble_count / total_events) * 100.0

            self._write_metric(client, project_name, "custom.googleapis.com/ml/cascade_fast_path_pct", fast_path_percent, {"target": "80"}, dry_run)

            self._write_metric(client, project_name, "custom.googleapis.com/ml/cascade_ensemble_pct", ensemble_percent, {"target": "20"}, dry_run)

            if dry_run or self.verbosity >= 1:
                self.stdout.write(
                    f"  Cascading: Fast path={fast_path_percent:.1f}% ({fast_path_count}), Ensemble={ensemble_percent:.1f}% ({ensemble_count})"
                )

            return 2

        return 0

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
