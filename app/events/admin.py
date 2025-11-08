from django.contrib import admin
from django.contrib.admin import display
from django.utils.html import format_html

from .models import AttendanceRecord, BoardingEvent


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
        "bus_route",
        "model_version",
    ]
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

    @display(description="Confirmation Faces")
    def get_confirmation_faces_thumbnails(self, obj):
        """Display 3 confirmation face thumbnails inline"""
        faces_html = []

        for i in range(1, 4):
            face_url = getattr(obj, f"confirmation_face_{i}_url", None)
            if face_url:
                faces_html.append(
                    f'<a href="{face_url}" target="_blank">'
                    f'<img src="{face_url}" style="width:40px;height:40px;object-fit:cover;'
                    f'border:1px solid #007bff;border-radius:3px;margin-right:2px;" '
                    f'title="Confirmation {i} (click to enlarge)"/>'
                    f"</a>"
                )
            else:
                faces_html.append(
                    f'<div style="width:40px;height:40px;background:#f8f9fa;'
                    f"border:1px solid #dee2e6;border-radius:3px;"
                    f"display:inline-flex;align-items:center;justify-content:center;"
                    f'font-size:8px;color:#adb5bd;margin-right:2px;" '
                    f'title="No face {i}">-</div>'
                )

        return format_html("".join(faces_html))

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
        """Boarding events are append-only, never delete"""
        return False


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
