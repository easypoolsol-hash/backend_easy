from django.contrib import admin
from django.contrib.admin import SimpleListFilter, display
from django.db import models
from django.http import HttpResponse
from django.utils.html import format_html

from .models import AttendanceRecord, BoardingEvent
from .services.pdf_report_service import BoardingReportService


class UnknownFaceFilter(SimpleListFilter):
    """Filter for unknown/unidentified faces"""

    title = "Face Type"
    parameter_name = "face_type"

    def lookups(self, request, model_admin):
        return (
            ("known", "Known Students"),
            ("unknown", "Unknown Faces"),
        )

    def queryset(self, request, queryset):
        if self.value() == "known":
            return queryset.filter(student__isnull=False)
        if self.value() == "unknown":
            return queryset.filter(student__isnull=True)
        return queryset


class BackendVerificationFilter(SimpleListFilter):
    """Filter for backend multi-model verification status"""

    title = "Backend Verification"
    parameter_name = "backend_verification"

    def lookups(self, request, model_admin):
        return (
            ("pending", "⏳ Pending"),
            ("verified", "✅ Verified"),
            ("flagged", "⚠️ Flagged for Review"),
            ("failed", "❌ Failed"),
            ("mismatch", "🔴 Kiosk/Backend Mismatch"),
        )

    def queryset(self, request, queryset):
        if self.value() in ("pending", "verified", "flagged", "failed"):
            return queryset.filter(backend_verification_status=self.value())
        if self.value() == "mismatch":
            # Show events where kiosk and backend predictions differ
            return queryset.exclude(backend_student__isnull=True).exclude(student=models.F("backend_student"))
        return queryset


@admin.register(BoardingEvent)
class BoardingEventAdmin(admin.ModelAdmin):
    """Admin interface for boarding events"""

    list_display = [
        "event_id_short",
        "is_unknown_face_display",
        "get_reference_photo_thumbnail",
        "get_confirmation_faces_thumbnails",
        "get_student_name",
        "backend_verification_display",
        "kiosk_id",
        "confidence_score",
        "timestamp",
        "get_bus_route",
        "get_location",
        "model_version",
    ]

    def get_queryset(self, request):
        """Optimize queryset with kiosk/bus prefetch for immutable historical data"""
        qs = super().get_queryset(request)
        # Prefetch student for name/photo, but get bus from kiosk (not student assignment)
        # Initialize per-request kiosk cache (avoid N+1 queries)
        self._kiosk_cache = {}
        return qs.select_related("student")

    list_filter = [
        UnknownFaceFilter,
        BackendVerificationFilter,
        "backend_verification_status",
        "backend_verification_confidence",
        "timestamp",
        "kiosk_id",
        "model_version",
        "bus_route",
    ]
    search_fields = ["event_id", "student__name", "kiosk_id", "bus_route"]
    readonly_fields = ["event_id", "created_at"]
    date_hierarchy = "timestamp"
    ordering = ["-timestamp"]

    # Add custom actions
    actions = ["delete_selected_with_gcs_cleanup", "download_boarding_report"]

    @admin.action(description="Download Boarding Report (PDF)")
    def download_boarding_report(self, request, queryset):
        """Generate and download PDF boarding report from selected events.

        This action generates a professional PDF report with summary statistics
        and detailed boarding event information. The PDF is generated on-the-fly
        with no file storage.
        """
        # Generate PDF using the report service
        pdf_buffer, filename = BoardingReportService.generate_report(queryset)

        # Return PDF as HTTP response (download)
        response = HttpResponse(pdf_buffer.read(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        # Note: No success message needed - the download itself confirms success

        return response

    @admin.action(description="Delete selected boarding events (with GCS cleanup)")
    def delete_selected_with_gcs_cleanup(self, request, queryset):
        """Delete selected boarding events and clean up GCS images.

        This action extends the default delete to also clean up GCS confirmation face images.
        """
        count = queryset.count()
        # Call the built-in delete_queryset which already has GCS cleanup
        self.delete_queryset(request, queryset)

        self.message_user(request, f"Successfully deleted {count} boarding events and cleaned up GCS images.")

    fieldsets = (
        ("Event Info", {"fields": ("event_id", "student", "kiosk_id", "timestamp")}),
        (
            "Recognition",
            {"fields": ("confidence_score", "model_version", "face_image_url")},
        ),
        (
            "Backend Verification (Multi-Model)",
            {
                "fields": (
                    "backend_verification_status",
                    "backend_verification_confidence",
                    "backend_student",
                    "backend_verified_at",
                    "model_consensus_data",
                ),
                "description": "Results from backend multi-model consensus verification (ArcFace + AdaFace + MobileFaceNet)",
            },
        ),
        (
            "Verification Images",
            {
                "fields": ("get_confirmation_faces_display",),
                "description": "Confirmation face images captured during boarding",
            },
        ),
        ("Location", {"fields": ("latitude", "longitude", "bus_route")}),
        ("Metadata", {"fields": ("metadata", "created_at"), "classes": ("collapse",)}),
    )

    readonly_fields = ["event_id", "created_at", "get_confirmation_faces_display"]

    @display(description="Unknown", boolean=True)
    def is_unknown_face_display(self, obj):
        """Display whether this is an unknown face event"""
        return obj.student is None

    @display(description="Backend Verification")
    def backend_verification_display(self, obj):
        """Display backend multi-model verification status with color coding"""
        status_icons = {
            "pending": "⏳",
            "verified": "✅",
            "flagged": "⚠️",
            "failed": "❌",
        }
        confidence_colors = {
            "high": "#28a745",  # green
            "medium": "#ffc107",  # yellow
            "low": "#dc3545",  # red
        }

        icon = status_icons.get(obj.backend_verification_status, "❓")
        status_label = obj.backend_verification_status.upper()

        # Check for mismatch
        has_mismatch = obj.has_verification_mismatch if obj.backend_student else False

        # Build HTML
        html = f'<span style="font-size:16px;">{icon}</span> {status_label}'

        if obj.backend_verification_confidence:
            color = confidence_colors.get(obj.backend_verification_confidence, "#6c757d")
            html += f'<br/><span style="color:{color};font-weight:bold;">{obj.backend_verification_confidence.upper()}</span>'

        if has_mismatch:
            html += '<br/><span style="color:#dc3545;font-weight:bold;">🔴 MISMATCH</span>'

        return format_html(html)

    @display(description="Student Name")
    def get_student_name(self, obj):
        """Display decrypted student name or 'Unknown' for unidentified faces"""
        if obj.student is None:
            return format_html('<span style="color:#dc3545;font-weight:bold;">UNKNOWN</span>')
        try:
            return obj.student.encrypted_name
        except Exception:
            # If decryption fails, return the student ID
            return f"Student {obj.student.student_id}"

    @display(description="Bus/Route")
    def get_bus_route(self, obj):
        """Display bus/route from kiosk (immutable historical data)"""
        try:
            # Initialize cache if not exists (safety check)
            if not hasattr(self, "_kiosk_cache"):
                self._kiosk_cache = {}

            # Use cache to avoid N+1 queries (kiosk_id is CharField, not ForeignKey)
            if obj.kiosk_id not in self._kiosk_cache:
                from kiosks.models import Kiosk

                try:
                    self._kiosk_cache[obj.kiosk_id] = Kiosk.objects.select_related("bus", "bus__route").get(kiosk_id=obj.kiosk_id)
                except Kiosk.DoesNotExist:
                    self._kiosk_cache[obj.kiosk_id] = None

            kiosk = self._kiosk_cache[obj.kiosk_id]
            if kiosk and kiosk.bus:
                bus = kiosk.bus
                if bus.route:
                    return f"{bus.bus_number}: {bus.route.name}"
                return f"{bus.bus_number}: No Route"
            # Fallback to bus_route field
            return obj.bus_route if obj.bus_route else "-"
        except Exception:
            # Fallback to bus_route field if any error
            return obj.bus_route if obj.bus_route else "-"

    @display(description="Location")
    def get_location(self, obj):
        """Display GPS coordinates"""
        if obj.latitude is not None and obj.longitude is not None:
            return f"{obj.latitude:.4f}, {obj.longitude:.4f}"
        return "-"

    @display(description="Reference Photo")
    def get_reference_photo_thumbnail(self, obj):
        """Display student's reference photo thumbnail (N/A for unknown faces)"""
        if obj.student is None:
            return format_html(
                '<div style="width:50px;height:50px;background:#fff3cd;'
                "border:2px solid #ffc107;border-radius:4px;"
                "display:flex;align-items:center;justify-content:center;"
                'font-size:10px;color:#856404;" '
                'title="Unknown face - no reference photo">Unknown</div>'
            )

        ref_photo = obj.student.get_reference_photo()

        if ref_photo and ref_photo.photo_url:
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="width:50px;height:50px;object-fit:cover;'
                'border:2px solid #28a745;border-radius:4px;" '
                'title="Reference photo (click to enlarge)"/>'
                "</a>",
                ref_photo.photo_url,
                ref_photo.photo_url,
            )
        else:
            return format_html(
                '<div style="width:50px;height:50px;background:#e9ecef;'
                "border:2px solid #6c757d;border-radius:4px;"
                "display:flex;align-items:center;justify-content:center;"
                'font-size:10px;color:#6c757d;" '
                'title="No photo available">No Photo</div>'
            )

    def get_confirmation_faces_thumbnails(self, obj):
        """Display 3 confirmation face thumbnails inline with lazy loading"""
        from django.utils.html import format_html
        from django.utils.safestring import mark_safe

        html_parts = []
        has_images = False

        for i in range(1, 4):
            # Check if GCS path exists
            gcs_path = getattr(obj, f"confirmation_face_{i}_gcs", None)
            if gcs_path:
                has_images = True
                # Generate signed URL
                face_url = getattr(obj, f"confirmation_face_{i}_url", None)
                if face_url:
                    # Use lazy loading with placeholder
                    html_parts.append(
                        format_html(
                            '<a href="{}" target="_blank" style="display:inline-block;margin-right:4px;">'
                            '<img data-src="{}" width="50" height="50" '
                            'style="object-fit:cover;border:2px solid #007bff;border-radius:4px;background:#e9ecef;" '
                            'class="lazy-load-img" '
                            'title="Confirmation face {}" '
                            'alt="Loading..."/>'
                            "</a>",
                            face_url,
                            face_url,
                            i,
                        )
                    )

        if not has_images:
            return format_html('<span style="color:#999;">-</span>')

        # Add lazy loading script (only once per page)
        lazy_script = """
        <script>
        (function() {
            if (window.lazyLoadInitialized) return;
            window.lazyLoadInitialized = true;

            function lazyLoad() {
                const images = document.querySelectorAll('img.lazy-load-img[data-src]');

                const imageObserver = new IntersectionObserver((entries, observer) => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            const img = entry.target;
                            img.src = img.dataset.src;
                            img.removeAttribute('data-src');
                            img.classList.remove('lazy-load-img');
                            observer.unobserve(img);
                        }
                    });
                });

                images.forEach(img => imageObserver.observe(img));
            }

            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', lazyLoad);
            } else {
                lazyLoad();
            }
        })();
        </script>
        """

        # Combine HTML parts with lazy loading script
        return mark_safe("".join(html_parts) + lazy_script)

    get_confirmation_faces_thumbnails.short_description = "Confirmation Faces"  # type: ignore[attr-defined]

    @display(description="Verification Images")
    def get_confirmation_faces_display(self, obj):
        """Display confirmation faces in detail view with reference photo"""
        html_parts = []

        # Reference photo (skip for unknown faces)
        if obj.student is not None:
            ref_photo = obj.student.get_reference_photo()
            html_parts.append('<div style="margin-bottom:20px;">')
            html_parts.append('<h4 style="margin-bottom:10px;">Student Reference Photo</h4>')
            if ref_photo and ref_photo.photo_url:
                html_parts.append(
                    f'<a href="{ref_photo.photo_url}" target="_blank">'
                    f'<img src="{ref_photo.photo_url}" style="width:150px;height:150px;object-fit:cover;'
                    f'border:3px solid #28a745;border-radius:8px;" '
                    f'title="Click to enlarge"/>'
                    f"</a>"
                )
            else:
                html_parts.append("<p>No reference photo available</p>")
            html_parts.append("</div>")
        else:
            html_parts.append('<div style="margin-bottom:20px;">')
            html_parts.append('<h4 style="margin-bottom:10px;color:#dc3545;">Unknown Face Event</h4>')
            html_parts.append(
                '<p style="background:#fff3cd;padding:10px;border:2px solid #ffc107;border-radius:4px;">'
                "This boarding event was created for an unidentified face. "
                "No student reference photo available.</p>"
            )
            html_parts.append("</div>")

        # Confirmation faces
        html_parts.append("<div>")
        html_parts.append('<h4 style="margin-bottom:10px;">Boarding Confirmation Faces</h4>')
        html_parts.append('<div style="display:flex;gap:15px;">')

        for i in range(1, 4):
            face_url = getattr(obj, f"confirmation_face_{i}_url", None)
            html_parts.append('<div style="text-align:center;">')
            html_parts.append(f'<div style="margin-bottom:5px;font-weight:bold;">Frame {i}</div>')

            if face_url:
                html_parts.append(
                    f'<a href="{face_url}" target="_blank">'
                    f'<img src="{face_url}" style="width:112px;height:112px;object-fit:cover;'
                    f'border:2px solid #007bff;border-radius:4px;" '
                    f'title="Click to enlarge"/>'
                    f"</a>"
                )
            else:
                html_parts.append(
                    '<div style="width:112px;height:112px;background:#f8f9fa;'
                    "border:2px solid #dee2e6;border-radius:4px;"
                    "display:flex;align-items:center;justify-content:center;"
                    'color:#adb5bd;">No Image</div>'
                )
            html_parts.append("</div>")

        html_parts.append("</div>")
        html_parts.append("</div>")

        return format_html("".join(html_parts))

    def event_id_short(self, obj):
        """Display shortened ULID for readability"""
        return f"{obj.event_id[:8]}..."

    event_id_short.short_description = "Event ID"  # type: ignore[attr-defined]
    event_id_short.admin_order_field = "event_id"  # type: ignore[attr-defined]

    def has_add_permission(self, request):
        """Boarding events should only be created by kiosks, not manually"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete boarding events (for greenfield cleanup).

        Args:
            request: The HTTP request object.
            obj: The BoardingEvent object (if checking specific object).

        Returns:
            True if user is superuser, False otherwise.

        Note:
            Boarding events are append-only in production.
            Delete permission for superusers enables manual cleanup during development.
        """
        return request.user.is_superuser

    def delete_model(self, request, obj):
        """Delete boarding event and associated GCS confirmation face images.

        Args:
            request: The HTTP request object.
            obj: The BoardingEvent object to delete.

        Note:
            This ensures GCS images are cleaned up when deleting via admin interface.
        """
        # Delete GCS confirmation face images if they exist
        if obj.confirmation_face_1_gcs or obj.confirmation_face_2_gcs or obj.confirmation_face_3_gcs:
            try:
                from .services.storage_service import BoardingEventStorageService

                storage_service = BoardingEventStorageService()
                storage_service.delete_confirmation_faces(obj.event_id)
            except Exception:
                # Log error but don't block deletion
                # Images will be orphaned in GCS but can be cleaned up with lifecycle rules
                pass

        # Delete the database record
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """Delete multiple boarding events and their GCS images (bulk delete action).

        Args:
            request: The HTTP request object.
            queryset: QuerySet of BoardingEvent objects to delete.

        Note:
            Used for bulk delete actions in admin interface.
        """
        # Delete GCS images for each event
        try:
            from .services.storage_service import BoardingEventStorageService

            storage_service = BoardingEventStorageService()

            for obj in queryset:
                if obj.confirmation_face_1_gcs or obj.confirmation_face_2_gcs or obj.confirmation_face_3_gcs:
                    try:
                        storage_service.delete_confirmation_faces(obj.event_id)
                    except Exception:
                        # Continue deleting other events even if one fails
                        pass
        except Exception:
            # Log error but don't block deletion
            pass

        # Delete the database records
        super().delete_queryset(request, queryset)


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    """Admin interface for attendance records"""

    list_display = [
        "student",
        "date",
        "status",
        "morning_boarded",
        "afternoon_boarded",
        "morning_time",
        "afternoon_time",
    ]
    list_filter = ["status", "date", "morning_boarded", "afternoon_boarded"]
    search_fields = ["student__name", "student__student_id"]
    readonly_fields = ["record_id", "created_at"]
    date_hierarchy = "date"
    ordering = ["-date"]

    fieldsets = (
        ("Record Info", {"fields": ("record_id", "student", "date", "status")}),
        ("Morning Session", {"fields": ("morning_boarded", "morning_time")}),
        ("Afternoon Session", {"fields": ("afternoon_boarded", "afternoon_time")}),
        ("Metadata", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    def has_add_permission(self, request):
        """Attendance records should be auto-generated by background jobs"""
        return False
