from django.contrib import admin
from django.contrib.admin import display
from django.http import HttpResponse
from django.utils.html import format_html

from .models import AttendanceRecord, BoardingEvent
from .services.pdf_report_service import BoardingReportService


@admin.register(BoardingEvent)
class BoardingEventAdmin(admin.ModelAdmin):
    """Admin interface for boarding events"""

    list_display = [
        "event_id_short",
        "get_reference_photo_thumbnail",
        "get_confirmation_faces_thumbnails",
        "get_student_name",
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

    @display(description="Student Name")
    def get_student_name(self, obj):
        """Display decrypted student name"""
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
            if not hasattr(self, '_kiosk_cache'):
                self._kiosk_cache = {}
            
            # Use cache to avoid N+1 queries (kiosk_id is CharField, not ForeignKey)
            if obj.kiosk_id not in self._kiosk_cache:
                from kiosks.models import Kiosk
                try:
                    self._kiosk_cache[obj.kiosk_id] = Kiosk.objects.select_related('bus', 'bus__route').get(kiosk_id=obj.kiosk_id)
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
        """Display student's reference photo thumbnail"""
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
        """Display 3 confirmation face thumbnails inline"""
        from django.utils.html import format_html
        from django.utils.safestring import mark_safe

        html_parts = []

        for i in range(1, 4):
            # Check if GCS path exists
            gcs_path = getattr(obj, f"confirmation_face_{i}_gcs", None)
            if gcs_path:
                # Generate signed URL
                face_url = getattr(obj, f"confirmation_face_{i}_url", None)
                if face_url:
                    html_parts.append(
                        format_html(
                            '<a href="{}" target="_blank" style="display:inline-block;margin-right:4px;">'
                            '<img src="{}" width="50" height="50" '
                            'style="object-fit:cover;border:2px solid #007bff;border-radius:4px;" '
                            'title="Confirmation face {}"/>'
                            "</a>",
                            face_url,
                            face_url,
                            i,
                        )
                    )

        if not html_parts:
            return format_html('<span style="color:#999;">-</span>')

        # Combine safe HTML parts using mark_safe
        return mark_safe("".join(html_parts))

    get_confirmation_faces_thumbnails.short_description = "Confirmation Faces"  # type: ignore[attr-defined]

    @display(description="Verification Images")
    def get_confirmation_faces_display(self, obj):
        """Display confirmation faces in detail view with reference photo"""
        ref_photo = obj.student.get_reference_photo()
        html_parts = []

        # Reference photo
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
