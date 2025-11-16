"""PDF Report Generation Service for Boarding Events.

Industry-standard PDF generation using WeasyPrint.
Generates professional boarding reports with summary statistics and detailed event lists.
"""

from collections import defaultdict
from io import BytesIO
from typing import Any

from django.db.models import QuerySet
from django.template.loader import render_to_string
from django.utils import timezone
from weasyprint import HTML

from events.models import BoardingEvent


class BoardingReportService:
    """Service for generating boarding event PDF reports.

    Uses WeasyPrint to convert HTML templates to professional PDFs.
    All generation is done in-memory with no file storage.
    """

    @staticmethod
    def generate_report(
        queryset: QuerySet[BoardingEvent],
        title: str = "Daily Boarding Report",
    ) -> tuple[BytesIO, str]:
        """Generate PDF report from boarding events queryset.

        Args:
            queryset: QuerySet of BoardingEvent objects (filtered by admin)
            title: Report title (default: "Daily Boarding Report")

        Returns:
            Tuple of (BytesIO PDF content, filename)

        Example:
            pdf_content, filename = BoardingReportService.generate_report(events_qs)
        """
        # Prefetch related data for performance
        events = queryset.select_related("student", "student__assigned_bus", "student__assigned_bus__route").order_by("timestamp")

        # Calculate summary statistics
        stats = BoardingReportService._calculate_statistics(events)

        # Group students by bus (one row per student)
        students_by_bus = BoardingReportService._group_students_by_bus(events)

        # Determine date range for filename
        date_range = BoardingReportService._get_date_range(events)

        # Render HTML template
        html_content = render_to_string(
            "reports/boarding_report.html",
            {
                "title": title,
                "generated_at": timezone.now(),
                "date_range": date_range,
                "stats": stats,
                "students_by_bus": students_by_bus,
            },
        )

        # Convert HTML to PDF using WeasyPrint
        pdf_buffer = BytesIO()
        HTML(string=html_content).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)

        # Generate filename
        filename = BoardingReportService._generate_filename(date_range)

        return pdf_buffer, filename

    @staticmethod
    def _calculate_statistics(events: QuerySet[BoardingEvent]) -> dict[str, Any]:
        """Calculate summary statistics from events.

        Args:
            events: QuerySet of BoardingEvent objects

        Returns:
            Dictionary with summary statistics
        """
        # Unique buses involved
        unique_buses = events.exclude(bus_route__isnull=True).exclude(bus_route="").values("bus_route").distinct().count()

        return {
            "total_events": events.count(),
            "unique_buses": unique_buses,
        }

    @staticmethod
    def _group_students_by_bus(events: QuerySet[BoardingEvent]) -> dict[str, Any]:
        """Group events by bus and show ALL events (including duplicates).

        Args:
            events: QuerySet of BoardingEvent objects

        Returns:
            Dictionary mapping bus info to event data with registered count
        """
        buses_data: dict[str, Any] = {}

        # Group events by bus first
        events_by_bus: dict[str, list[BoardingEvent]] = defaultdict(list)

        for event in events:
            assigned_bus = event.student.assigned_bus

            if assigned_bus:
                bus_number = getattr(assigned_bus, "bus_number", None)
                route = getattr(assigned_bus, "route", None)

                if bus_number and route and hasattr(route, "name"):
                    bus_key = f"Bus {bus_number} - {route.name}"  # type: ignore[attr-defined]
                elif bus_number:
                    bus_key = f"Bus {bus_number}"
                else:
                    bus_key = "Unknown Bus"

                events_by_bus[bus_key].append(event)
            else:
                events_by_bus["Unknown Bus"].append(event)

        # For each bus, show ALL events (including multiple scans of same student)
        for bus_key, bus_events in events_by_bus.items():
            # Convert events to display format (show ALL events)
            events_list = []
            bus_obj = None

            for event in bus_events:
                student = event.student

                events_list.append(
                    {
                        "student": student,
                        "timestamp": event.timestamp,
                        "bus_number": getattr(student.assigned_bus, "bus_number", "N/A") if student.assigned_bus else "N/A",
                    }
                )

                # Store bus object for getting registered count
                if student.assigned_bus and not bus_obj:
                    bus_obj = student.assigned_bus

            # Get total registered students for this bus
            registered_count: int = 0
            if bus_obj:
                # Access related_name from Bus model: "assigned_students"
                students_manager = getattr(bus_obj, "assigned_students", None)
                if students_manager is not None:
                    registered_count = students_manager.count()

            buses_data[bus_key] = {
                "students": events_list,  # Keep name as "students" for template compatibility
                "registered_count": registered_count,
            }

        # Sort by bus name
        return dict(sorted(buses_data.items()))

    @staticmethod
    def _get_date_range(events: QuerySet[BoardingEvent]) -> dict[str, Any]:
        """Get date range from events queryset.

        Args:
            events: QuerySet of BoardingEvent objects

        Returns:
            Dictionary with start_date, end_date, and display string
        """
        if not events.exists():
            today = timezone.now().date()
            return {
                "start_date": today,
                "end_date": today,
                "display": today.strftime("%B %d, %Y"),
            }

        timestamps = events.values_list("timestamp", flat=True)
        start_date = min(timestamps).date()
        end_date = max(timestamps).date()

        if start_date == end_date:
            display = start_date.strftime("%B %d, %Y")
        else:
            display = f"{start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}"

        return {
            "start_date": start_date,
            "end_date": end_date,
            "display": display,
        }

    @staticmethod
    def _generate_filename(date_range: dict[str, Any]) -> str:
        """Generate PDF filename from date range.

        Args:
            date_range: Dictionary with start_date and end_date

        Returns:
            Filename string (e.g., "boarding_report_2025-01-16.pdf")
        """
        start = date_range["start_date"]
        end = date_range["end_date"]

        if start == end:
            return f"boarding_report_{start.isoformat()}.pdf"
        else:
            return f"boarding_report_{start.isoformat()}_to_{end.isoformat()}.pdf"
