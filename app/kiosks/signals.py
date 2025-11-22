"""
Kiosk Real-time Metrics Streaming to Cloud Monitoring

Streams kiosk health metrics to Cloud Monitoring immediately when heartbeat updates.
Dashboard updates in real-time when kiosk sends heartbeat.
"""

import logging
import os
import threading

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


def export_kiosk_metrics_async(kiosk_status):
    """Export metrics in background thread to not block heartbeat response"""
    try:
        from google.cloud import monitoring_v3

        client = monitoring_v3.MetricServiceClient()
        project_id = os.environ.get("GCP_PROJECT_ID", "easypool-backend")
        project_name = f"projects/{project_id}"

        kiosk = kiosk_status.kiosk
        status = kiosk_status

        # Prepare metric data
        metrics = []

        # Battery level
        if status.battery_level is not None:
            metrics.append(
                {
                    "type": "custom.googleapis.com/kiosk/battery_level",
                    "value": float(status.battery_level),
                    "labels": {
                        "kiosk_id": kiosk.kiosk_id,
                        "bus_route": kiosk.bus.route.name if kiosk.bus and kiosk.bus.route else "unknown",
                        "is_charging": str(status.is_charging).lower(),
                    },
                }
            )

        # Temperature
        if status.device_temperature is not None:
            temp_celsius = status.device_temperature / 10.0
            metrics.append(
                {
                    "type": "custom.googleapis.com/kiosk/temperature",
                    "value": temp_celsius,
                    "labels": {
                        "kiosk_id": kiosk.kiosk_id,
                        "bus_route": kiosk.bus.route.name if kiosk.bus and kiosk.bus.route else "unknown",
                    },
                }
            )

        # Storage
        if status.storage_available_mb is not None:
            metrics.append(
                {
                    "type": "custom.googleapis.com/kiosk/storage_available",
                    "value": float(status.storage_available_mb),
                    "labels": {"kiosk_id": kiosk.kiosk_id},
                }
            )

        # Network quality
        network_quality = {"5g": 4, "wifi": 3, "4g": 2, "3g": 1, "none": 0, None: 0}.get(status.network_type, 0)
        metrics.append(
            {
                "type": "custom.googleapis.com/kiosk/network_quality",
                "value": network_quality,
                "labels": {
                    "kiosk_id": kiosk.kiosk_id,
                    "network_type": status.network_type or "none",
                },
                "is_int": True,
            }
        )

        # Write all metrics
        now = timezone.now()
        for metric in metrics:
            series = monitoring_v3.TimeSeries()
            series.metric.type = metric["type"]
            series.resource.type = "generic_node"
            series.resource.labels["project_id"] = project_id
            series.resource.labels["location"] = "global"
            series.resource.labels["namespace"] = "kiosk"
            series.resource.labels["node_id"] = metric["labels"].get("kiosk_id", "unknown")

            for key, val in metric["labels"].items():
                series.metric.labels[key] = str(val)

            interval = monitoring_v3.TimeInterval({"end_time": {"seconds": int(now.timestamp())}})

            if metric.get("is_int"):
                point_value = {"int64_value": int(metric["value"])}
            else:
                point_value = {"double_value": float(metric["value"])}

            point = monitoring_v3.Point({"interval": interval, "value": point_value})
            series.points = [point]

            client.create_time_series(name=project_name, time_series=[series])

        logger.info(f"Streamed {len(metrics)} metrics for kiosk {kiosk.kiosk_id} to Cloud Monitoring")

    except Exception as e:
        logger.error(f"Failed to export kiosk metrics: {e}", exc_info=True)


@receiver(post_save, sender="kiosks.KioskStatus")
def stream_kiosk_metrics_to_cloud_monitoring(sender, instance, **kwargs):
    """
    Stream kiosk health metrics to Cloud Monitoring on heartbeat.
    Dashboard updates in real-time when new heartbeat is received.
    """
    # Only stream if enabled (production/dev environments)
    if not getattr(settings, "KIOSK_METRICS_STREAMING_ENABLED", False):
        return

    # Run in background thread to not block response
    thread = threading.Thread(target=export_kiosk_metrics_async, args=(instance,))
    thread.daemon = True
    thread.start()
