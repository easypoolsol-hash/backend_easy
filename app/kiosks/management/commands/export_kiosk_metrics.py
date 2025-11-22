"""
Export Kiosk Health Metrics to Google Cloud Monitoring

Run this command periodically (via Cloud Scheduler or Celery Beat) to export
kiosk health metrics to Cloud Monitoring for dashboards and alerting.

Usage:
    python manage.py export_kiosk_metrics
"""

import logging
import os

from django.core.management.base import BaseCommand
from django.utils import timezone
from google.cloud import monitoring_v3  # type: ignore[attr-defined]

from kiosks.models import Kiosk

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Export kiosk health metrics to Google Cloud Monitoring"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print metrics without sending to Cloud Monitoring",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No metrics will be sent"))

        try:
            # Initialize Cloud Monitoring client
            client = monitoring_v3.MetricServiceClient()
            project_id = os.environ.get("GCP_PROJECT_ID", "easypool-backend")
            project_name = f"projects/{project_id}"

            # Get all active kiosks with their latest status
            kiosks = Kiosk.objects.select_related("status", "bus", "bus__route").filter(is_active=True)

            metrics_sent = 0
            for kiosk in kiosks:
                if not hasattr(kiosk, "status") or not kiosk.status:
                    continue

                status = kiosk.status

                # Export battery level
                self._write_metric(
                    client,
                    project_name,
                    "custom.googleapis.com/kiosk/battery_level",
                    status.battery_level if status.battery_level is not None else 0.0,
                    {
                        "kiosk_id": kiosk.kiosk_id,
                        "bus_route": kiosk.bus.route.name if kiosk.bus and kiosk.bus.route else "unknown",
                        "is_charging": str(status.is_charging).lower(),
                    },
                    dry_run,
                )
                metrics_sent += 1

                # Export device temperature (convert from deciselsius to Celsius)
                if status.device_temperature is not None:
                    temp_celsius = status.device_temperature / 10.0
                    self._write_metric(
                        client,
                        project_name,
                        "custom.googleapis.com/kiosk/temperature",
                        temp_celsius,
                        {
                            "kiosk_id": kiosk.kiosk_id,
                            "bus_route": kiosk.bus.route.name if kiosk.bus and kiosk.bus.route else "unknown",
                        },
                        dry_run,
                    )
                    metrics_sent += 1

                # Export storage available
                if status.storage_available_mb is not None:
                    self._write_metric(
                        client,
                        project_name,
                        "custom.googleapis.com/kiosk/storage_available",
                        status.storage_available_mb,
                        {
                            "kiosk_id": kiosk.kiosk_id,
                        },
                        dry_run,
                    )
                    metrics_sent += 1

                # Export network quality (map network_type to quality score)
                network_quality = self._network_type_to_quality(status.network_type)
                self._write_metric(
                    client,
                    project_name,
                    "custom.googleapis.com/kiosk/network_quality",
                    network_quality,
                    {
                        "kiosk_id": kiosk.kiosk_id,
                        "network_type": status.network_type or "none",
                    },
                    dry_run,
                )
                metrics_sent += 1

            self.stdout.write(self.style.SUCCESS(f"✓ Exported {metrics_sent} metrics from {kiosks.count()} kiosks"))

        except Exception as e:
            logger.error(f"Failed to export kiosk metrics: {e}", exc_info=True)
            self.stdout.write(self.style.ERROR(f"✗ Failed to export metrics: {e}"))
            raise

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
        series.resource.labels["namespace"] = "kiosk"
        series.resource.labels["node_id"] = labels.get("kiosk_id", "unknown")

        # Add custom labels
        for key, val in labels.items():
            series.metric.labels[key] = str(val)

        # Add data point
        now = timezone.now()
        interval = monitoring_v3.TimeInterval({"end_time": {"seconds": int(now.timestamp())}})

        # Use int64_value for INT64 metrics, double_value for DOUBLE metrics
        # This must match the value_type in the metric descriptor definitions
        int64_metrics = {"custom.googleapis.com/kiosk/network_quality"}
        if metric_type in int64_metrics:
            point_value = {"int64_value": int(value)}
        else:
            point_value = {"double_value": float(value)}

        point = monitoring_v3.Point(
            {
                "interval": interval,
                "value": point_value,
            }
        )
        series.points = [point]

        # Write to Cloud Monitoring
        client.create_time_series(name=project_name, time_series=[series])

    def _network_type_to_quality(self, network_type):
        """Map network type to quality score"""
        mapping = {
            "5g": 4,
            "wifi": 3,
            "4g": 2,
            "3g": 1,
            "none": 0,
            None: 0,
        }
        return mapping.get(network_type, 0)
