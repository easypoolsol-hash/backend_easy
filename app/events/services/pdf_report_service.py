"""PDF Report Generation Service for Boarding Events.

Industry-standard PDF generation using WeasyPrint.
Generates professional boarding reports with summary statistics and detailed event lists.
"""

from collections import defaultdict
from io import BytesIO

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

        # Group events by bus/route for organized display
        events_by_bus = BoardingReportService._group_events_by_bus(events)

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
                "events_by_bus": events_by_bus,
                "total_events": events.count(),
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
    def _calculate_statistics(events: QuerySet[BoardingEvent]) -> dict:
        """Calculate summary statistics from events.

        Args:
            events: QuerySet of BoardingEvent objects

        Returns:
            Dictionary with summary statistics
        """
        # Unique students who boarded
        unique_students = events.values("student").distinct().count()

        # Unique buses involved
        unique_buses = events.exclude(bus_route__isnull=True).exclude(bus_route="").values("bus_route").distinct().count()

        # Average confidence score
        confidence_scores = [event.confidence_score for event in events if event.confidence_score is not None]
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0

        return {
            "total_events": events.count(),
            "unique_students": unique_students,
            "unique_buses": unique_buses,
            "avg_confidence": round(avg_confidence, 2),
        }

    @staticmethod
    def _group_events_by_bus(events: QuerySet[BoardingEvent]) -> dict:
        """Group events by bus route for organized display.

        Args:
            events: QuerySet of BoardingEvent objects

        Returns:
            Dictionary mapping bus routes to lists of events
        """
        events_by_bus = defaultdict(list)

        for event in events:
            # Determine bus identifier
            if event.bus_route:
                bus_key = event.bus_route
            else:
                # Mypy type narrowing: check if bus exists and has license_plate
                assigned_bus = event.student.assigned_bus
                if assigned_bus and hasattr(assigned_bus, "license_plate") and assigned_bus.license_plate:  # type: ignore[attr-defined]
                    bus_key = f"Bus {assigned_bus.license_plate}"  # type: ignore[attr-defined]
                else:
                    bus_key = "Unknown Bus"

            events_by_bus[bus_key].append(event)

        # Sort by bus name
        return dict(sorted(events_by_bus.items()))

    @staticmethod
    def _get_date_range(events: QuerySet[BoardingEvent]) -> dict:
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
    def _generate_filename(date_range: dict) -> str:
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
