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
                    "model_consensus_display",
                ),
                "description": "Results from backend multi-model consensus verification (MobileFaceNet + ArcFace INT8)",
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

    readonly_fields = ["event_id", "created_at", "get_confirmation_faces_display", "model_consensus_display"]

    @display(description="Unknown", boolean=True)
    def is_unknown_face_display(self, obj):
        """Display whether this is an unknown face event"""
        return obj.student is None

    @display(description="Backend Verification")
    def backend_verification_display(self, obj):
        """Display backend multi-model verification status with color coding and model scores"""
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

        # Add compact model scores OR pending model info
        if obj.backend_verification_status == "pending":
            # Show which models will process this + kiosk prediction
            html += '<br/><small style="font-size:10px;color:#6c757d;">Awaiting: MFN + ARC</small>'
            if obj.student:
                html += f'<br/><small style="font-size:10px;color:#007bff;">Kiosk: S{obj.student.student_id} ({obj.confidence_score:.2f})</small>'
        else:
            # Show actual model results after verification
            consensus_data = self._parse_model_consensus(obj)
            if consensus_data:
                scores_parts = []
                for model_name, prediction in consensus_data["predictions"].items():
                    student_id = prediction["student_id"]
                    score = prediction["score"]

                    # Abbreviate model name
                    abbrev = model_name[:3].upper()

                    if student_id:
                        # Color code score
                        if score >= 0.7:
                            score_color = "#28a745"  # green
                        elif score >= 0.5:
                            score_color = "#ffc107"  # yellow
                        else:
                            score_color = "#dc3545"  # red

                        scores_parts.append(
                            f'<span style="color:{score_color};font-weight:bold;" title="{model_name}: Student {student_id}">'
                            f"{abbrev}: {score:.2f}</span>"
                        )
                    else:
                        scores_parts.append(f'<span style="color:#dc3545;" title="{model_name}: No match">{abbrev}: ✗</span>')

                if scores_parts:
                    html += f'<br/><small style="font-size:10px;">{" | ".join(scores_parts)}</small>'

        if has_mismatch:
            html += '<br/><span style="color:#dc3545;font-weight:bold;">🔴 MISMATCH</span>'

        return format_html(html)

    @display(description="Model Consensus Results")
    def model_consensus_display(self, obj):
        """Display detailed results from each model in multi-model consensus"""
        if not obj.model_consensus_data:
            return format_html('<span style="color: gray;">No consensus data available</span>')

        try:
            import json

            # Parse consensus data
            consensus = obj.model_consensus_data if isinstance(obj.model_consensus_data, dict) else json.loads(obj.model_consensus_data)
            model_results = consensus.get("model_results", {})

            if not model_results:
                return format_html('<span style="color: gray;">No model results</span>')

            # Build HTML table
            html_parts = []
            html_parts.append('<table style="width:100%; border-collapse: collapse; margin-top: 10px;">')
            html_parts.append(
                '<thead><tr style="background: #f5f5f5;">'
                '<th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Model</th>'
                '<th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Predicted Student</th>'
                '<th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Confidence</th>'
                '<th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Top 3 Matches</th>'
                "</tr></thead><tbody>"
            )

            for model_name, result in model_results.items():
                student_id = result.get("student_id")
                confidence = result.get("confidence_score", 0.0)
                top_scores = result.get("top_5_scores", {})

                # Color code confidence
                if confidence >= 0.7:
                    conf_color = "#28a745"  # green
                elif confidence >= 0.5:
                    conf_color = "#ffc107"  # yellow
                else:
                    conf_color = "#dc3545"  # red

                # Student ID cell
                if student_id:
                    student_cell = f"<strong>{student_id}</strong>"
                else:
                    student_cell = '<span style="color: #dc3545;">No match</span>'

                # Confidence cell
                conf_cell = f'<span style="color: {conf_color}; font-weight: bold;">{confidence:.3f}</span>'

                # Top scores cell
                top_3 = list(top_scores.items())[:3]
                if top_3:
                    scores_html = "<br/>".join([f"ID {sid}: {score:.3f}" for sid, score in top_3])
                else:
                    scores_html = '<span style="color: gray;">-</span>'

                html_parts.append(
                    f"<tr>"
                    f'<td style="padding: 8px; border: 1px solid #ddd;"><strong>{model_name}</strong></td>'
                    f'<td style="padding: 8px; border: 1px solid #ddd;">{student_cell}</td>'
                    f'<td style="padding: 8px; border: 1px solid #ddd;">{conf_cell}</td>'
                    f'<td style="padding: 8px; border: 1px solid #ddd; font-size: 11px;">{scores_html}</td>'
                    f"</tr>"
                )

            html_parts.append("</tbody></table>")

            # Add consensus summary
            consensus_count = consensus.get("consensus_count", 0)
            total_models = len(model_results)
            html_parts.append(
                f'<div style="margin-top: 10px; padding: 8px; background: #f9f9f9; border-left: 4px solid #007bff;">'
                f"<strong>Consensus:</strong> {consensus_count}/{total_models} models agreed"
                f"</div>"
            )

            return format_html("".join(html_parts))

        except Exception as e:
            return format_html(f'<span style="color: red;">Error displaying consensus data: {e}</span>')

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

    def _parse_model_consensus(self, obj):
        """Parse model consensus data and check for disagreement"""
        if not obj.model_consensus_data:
            return None

        try:
            import json

            consensus = obj.model_consensus_data if isinstance(obj.model_consensus_data, dict) else json.loads(obj.model_consensus_data)
            model_results = consensus.get("model_results", {})

            if not model_results:
                return None

            # Extract predictions from each model
            predictions = {}
            for model_name, result in model_results.items():
                predictions[model_name] = {
                    "student_id": result.get("student_id"),
                    "score": result.get("confidence_score", 0.0),
                }

            # Check if models disagree
            unique_students = {p["student_id"] for p in predictions.values() if p["student_id"]}
            has_disagreement = len(unique_students) > 1

            return {"predictions": predictions, "has_disagreement": has_disagreement, "unique_students": unique_students}

        except Exception:
            return None

    @display(description="Reference Photo")
    def get_reference_photo_thumbnail(self, obj):
        """Display reference photo(s) - multiple if models disagree"""
        # Check for model disagreement
        consensus_data = self._parse_model_consensus(obj)

        if consensus_data and consensus_data["has_disagreement"]:
            # Models disagree - show multiple photos
            return self._render_multiple_reference_photos(consensus_data)

        # Models agree or unknown face - show single photo
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
            photo_url = ref_photo.get_cached_url()
            return format_html(
                '<a href="{}" target="_blank">'
                '<img data-src="{}" class="lazy-photo" '
                "src=\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
                "width='50' height='50'%3E%3Crect fill='%23e9ecef' "
                "width='50' height='50'/%3E%3C/svg%3E\" "
                'style="width:50px;height:50px;object-fit:cover;'
                'border:2px solid #28a745;border-radius:4px;" '
                'title="Reference photo (click to enlarge)" '
                'alt="Loading..."/>'
                "</a>",
                photo_url,
                photo_url,
            )
        else:
            return format_html(
                '<div style="width:50px;height:50px;background:#e9ecef;'
                "border:2px solid #6c757d;border-radius:4px;"
                "display:flex;align-items:center;justify-content:center;"
                'font-size:10px;color:#6c757d;" '
                'title="No photo available">No Photo</div>'
            )

    def _render_multiple_reference_photos(self, consensus_data):
        """Render multiple reference photos when models disagree"""
        from students.models import Student

        html_parts = ['<div style="display:flex;flex-direction:column;gap:6px;font-size:11px;max-width:120px;">']

        for model_name, prediction in consensus_data["predictions"].items():
            student_id = prediction["student_id"]
            score = prediction["score"]

            if not student_id:
                html_parts.append(f'<div style="padding:4px;border-left:2px solid #dc3545;"><strong>{model_name[:3]}</strong>: No match</div>')
                continue

            try:
                student = Student.objects.select_related().get(pk=student_id)
                ref_photo = student.get_reference_photo()

                html_parts.append('<div style="border-left:2px solid #ffc107;padding-left:6px;">')
                html_parts.append(f"<strong>{model_name[:3]}</strong>: S{student_id}<br/>")

                if ref_photo:
                    photo_url = ref_photo.get_cached_url()
                    html_parts.append(
                        f'<a href="{photo_url}" target="_blank">'
                        f'<img data-src="{photo_url}" class="lazy-photo" '
                        f"src=\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
                        f"width='40' height='40'%3E%3Crect fill='%23e9ecef' "
                        f"width='40' height='40'/%3E%3C/svg%3E\" "
                        f'style="width:40px;height:40px;border-radius:3px;margin:3px 0;object-fit:cover;" '
                        f'alt="Loading..." />'
                        f"</a>"
                    )
                    html_parts.append(f'<small style="color:#6c757d;">({score:.2f})</small>')
                else:
                    html_parts.append('<small style="color:#999;">No photo</small>')

                html_parts.append("</div>")

            except Student.DoesNotExist:
                html_parts.append(
                    f'<div style="padding:4px;border-left:2px solid #dc3545;"><strong>{model_name[:3]}</strong>: S{student_id} (not found)</div>'
                )

        html_parts.append("</div>")
        return format_html("".join(html_parts))

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
                // Handle both confirmation faces (.lazy-load-img) and reference photos (.lazy-photo)
                const images = document.querySelectorAll('img.lazy-load-img[data-src], img.lazy-photo[data-src]');

                const imageObserver = new IntersectionObserver((entries, observer) => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            const img = entry.target;
                            img.src = img.dataset.src;
                            img.removeAttribute('data-src');
                            img.classList.remove('lazy-load-img', 'lazy-photo');
                            observer.unobserve(img);
                        }
                    });
                }, {
                    rootMargin: '50px'  // Start loading 50px before visible
                });

                images.forEach(img => imageObserver.observe(img));

                // Re-observe when new content loads (e.g., pagination)
                const mutationObserver = new MutationObserver(() => {
                    const newImages = document.querySelectorAll('img.lazy-load-img[data-src], img.lazy-photo[data-src]');
                    newImages.forEach(img => {
                        if (!img.dataset.observed) {
                            imageObserver.observe(img);
                            img.dataset.observed = 'true';
                        }
                    });
                });

                mutationObserver.observe(document.body, {
                    childList: true,
                    subtree: true
                });
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
