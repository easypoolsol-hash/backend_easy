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
    actions = [
        "delete_selected_with_gcs_cleanup",
        "download_boarding_report",
        "trigger_verification",
        "export_selected_to_bigquery",
        "export_last_hour_to_bigquery",
    ]

    @admin.action(description="🔍 Verify Now (Multi-Crop)")
    def trigger_verification(self, request, queryset):
        """Manually trigger multi-crop verification for selected pending events.

        Runs the new multi-crop voting verification synchronously.
        Only processes events with 'pending' status.
        """
        from face_verification.tasks import verify_boarding_event

        pending_events = queryset.filter(backend_verification_status="pending")
        total = pending_events.count()

        if total == 0:
            self.message_user(request, "No pending events selected.", level="warning")
            return

        success_count = 0
        failed_count = 0

        for event in pending_events:
            try:
                result = verify_boarding_event(str(event.event_id))
                if result.get("status") == "success":
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                failed_count += 1
                self.message_user(request, f"Error verifying {event.event_id}: {e}", level="error")

        self.message_user(request, f"Verification complete: {success_count} verified, {failed_count} failed out of {total} events.")

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
        """Simple list view: Status + Student + Kiosk/Backend scores + Vote count"""
        import json

        # Status icons
        status_icons = {"pending": "⏳", "verified": "✅", "flagged": "⚠️", "failed": "❌"}
        icon = status_icons.get(obj.backend_verification_status, "❓")

        # Kiosk score
        kiosk_score = obj.confidence_score or 0.0
        kiosk_student = obj.student.name if obj.student else "?"

        if obj.backend_verification_status == "pending":
            html = f'{icon} <span style="color:#6c757d;">PENDING</span>'
            html += f"<br/><small>K:{kiosk_student}@{kiosk_score:.2f}</small>"
            return format_html(html)

        # Parse backend results - show student name if available
        backend_student = str(obj.backend_student) if obj.backend_student else "?"
        backend_score = 0.0
        vote_info = ""

        if obj.model_consensus_data:
            try:
                consensus = obj.model_consensus_data if isinstance(obj.model_consensus_data, dict) else json.loads(obj.model_consensus_data)
                backend_score = consensus.get("confidence_score", 0.0)
                voting = consensus.get("voting_details", {})
                total_crops = voting.get("total_crops", 0)
                vote_dist = voting.get("vote_distribution", {})
                # Get winning vote count
                if vote_dist:
                    max_votes = max(vote_dist.values()) if vote_dist.values() else 0
                    vote_info = f"{max_votes}/{total_crops}"
            except Exception:
                pass

        # Color code scores
        def score_color(s):
            return "#28a745" if s >= 0.7 else "#ffc107" if s >= 0.5 else "#dc3545"

        # Check mismatch
        has_mismatch = obj.backend_student and str(obj.student.student_id if obj.student else "") != str(obj.backend_student)
        match_icon = "🔴" if has_mismatch else ""

        # Build compact display
        html = f"{icon} {backend_student} {match_icon}"
        html += '<br/><small style="font-size:11px;">'
        html += f'K:<span style="color:{score_color(kiosk_score)}">{kiosk_score:.2f}</span> '
        html += f'B:<span style="color:{score_color(backend_score)}">{backend_score:.2f}</span>'
        if vote_info:
            html += f" [{vote_info}]"
        html += "</small>"

        return format_html(html)

    @display(description="Investigation View")
    def model_consensus_display(self, obj):
        """Detailed investigation view: Kiosk vs Backend with per-frame scores"""
        import json

        def score_color(s):
            return "#28a745" if s >= 0.7 else "#ffc107" if s >= 0.5 else "#dc3545"

        html = []

        # === KIOSK SECTION ===
        kiosk_score = obj.confidence_score or 0.0
        kiosk_student_id = str(obj.student.student_id) if obj.student else "Unknown"
        kiosk_name = ""
        try:
            kiosk_name = obj.student.encrypted_name if obj.student else ""
        except Exception:
            pass
        kiosk_model = obj.model_version or "MobileFaceNet"

        html.append('<div style="margin-bottom:15px;padding:10px;background:#e3f2fd;border-radius:4px;">')
        html.append('<h4 style="margin:0 0 8px 0;color:#1565c0;">📱 KIOSK PREDICTION</h4>')
        html.append('<table style="width:100%;border-collapse:collapse;">')
        html.append(f'<tr><td style="padding:4px;"><strong>Model:</strong></td><td>{kiosk_model}</td></tr>')
        html.append(f'<tr><td style="padding:4px;"><strong>Student:</strong></td><td><strong>{kiosk_name or kiosk_student_id}</strong></td></tr>')
        sc = score_color(kiosk_score)
        html.append('<tr><td style="padding:4px;"><strong>Score:</strong></td>')
        html.append(f'<td><span style="color:{sc};font-weight:bold;font-size:16px;">{kiosk_score:.4f}</span></td></tr>')
        html.append("</table></div>")

        # === BACKEND SECTION ===
        if not obj.model_consensus_data:
            html.append('<div style="padding:15px;background:#fff3e0;border-radius:4px;color:#e65100;">⏳ Backend verification pending...</div>')
            return format_html("".join(html))

        try:
            consensus = obj.model_consensus_data if isinstance(obj.model_consensus_data, dict) else json.loads(obj.model_consensus_data)

            # Check for failure reason first
            failure_reason = consensus.get("failure_reason")
            if failure_reason:
                html.append('<div style="padding:15px;background:#f8d7da;border:2px solid #dc3545;border-radius:4px;">')
                html.append('<h4 style="margin:0 0 8px 0;color:#721c24;">❌ BACKEND VERIFICATION FAILED</h4>')
                html.append(f'<p style="color:#721c24;margin:0;"><strong>Reason:</strong> {failure_reason}</p>')
                html.append("</div>")
                return format_html("".join(html))

            voting = consensus.get("voting_details", {})
            crop_results = voting.get("crop_results", [])
            model_results = consensus.get("model_results", {})
            backend_score = consensus.get("confidence_score", 0.0)

            # Check for empty results (verification ran but failed)
            if not crop_results and not model_results:
                reason = voting.get("reason", "unknown")
                html.append('<div style="padding:15px;background:#f8d7da;border:2px solid #dc3545;border-radius:4px;">')
                html.append('<h4 style="margin:0 0 8px 0;color:#721c24;">❌ BACKEND VERIFICATION FAILED</h4>')
                html.append(f'<p style="color:#721c24;margin:0;"><strong>Reason:</strong> {reason}</p>')
                html.append('<p style="color:#721c24;margin:5px 0 0 0;font-size:12px;">No crop images could be processed.</p>')
                html.append("</div>")
                return format_html("".join(html))

            html.append('<div style="margin-bottom:15px;padding:10px;background:#000;border-radius:4px;">')
            html.append('<h4 style="margin:0 0 8px 0;color:#fff;">🔍 BACKEND MULTI-CROP VERIFICATION</h4>')

            # Per-crop results table
            if crop_results:
                html.append('<table style="width:100%;border-collapse:collapse;margin-bottom:10px;">')
                html.append('<tr style="background:#333;">')
                html.append('<th style="padding:8px;border:1px solid #555;text-align:left;color:#fff;">Frame</th>')
                html.append('<th style="padding:8px;border:1px solid #555;text-align:left;color:#fff;">Matched</th>')
                html.append('<th style="padding:8px;border:1px solid #555;text-align:left;color:#fff;">Score</th>')
                html.append('<th style="padding:8px;border:1px solid #555;text-align:left;color:#fff;">Confidence</th>')
                html.append("</tr>")

                for crop in crop_results:
                    crop_idx = crop.get("crop", "?")
                    crop_student_id = crop.get("student_id")

                    # Get student name from UUID
                    crop_student = "No match"
                    if crop_student_id:
                        try:
                            from students.models import Student

                            crop_student_obj = Student.objects.get(student_id=crop_student_id)
                            crop_student = f"{crop_student_obj.encrypted_name} ({str(crop_student_id)[:8]}...)"
                        except Exception:
                            crop_student = f"{str(crop_student_id)[:8]}..."

                    crop_score = crop.get("score", 0.0)
                    crop_conf = crop.get("confidence", "low")
                    conf_colors = {"high": "#28a745", "medium": "#ffc107", "low": "#dc3545"}

                    sc = score_color(crop_score)
                    cc = conf_colors.get(crop_conf, "#999")
                    html.append('<tr style="background:#222;">')
                    html.append(f'<td style="padding:8px;border:1px solid #555;color:#fff;">Frame {crop_idx}</td>')
                    html.append(f'<td style="padding:8px;border:1px solid #555;color:#fff;"><strong>{crop_student}</strong></td>')
                    html.append('<td style="padding:8px;border:1px solid #555;">')
                    html.append(f'<span style="color:{sc};font-weight:bold;">{crop_score:.4f}</span></td>')
                    html.append('<td style="padding:8px;border:1px solid #555;">')
                    html.append(f'<span style="color:{cc};">{crop_conf.upper()}</span></td>')
                    html.append("</tr>")

                html.append("</table>")

            # Model breakdown from best crop
            if model_results:
                html.append('<h5 style="margin:10px 0 5px 0;color:#fff;">Model Breakdown (Best Crop):</h5>')
                html.append('<table style="width:100%;border-collapse:collapse;">')
                html.append('<tr style="background:#333;">')
                html.append('<th style="padding:6px;border:1px solid #555;text-align:left;color:#fff;">Model</th>')
                html.append('<th style="padding:6px;border:1px solid #555;text-align:left;color:#fff;">Student</th>')
                html.append('<th style="padding:6px;border:1px solid #555;text-align:left;color:#fff;">Score</th>')
                html.append("</tr>")

                for model_name, result in model_results.items():
                    m_student_id = result.get("student_id")

                    # Get student name from UUID
                    m_student = "-"
                    if m_student_id:
                        try:
                            from students.models import Student

                            m_student_obj = Student.objects.get(student_id=m_student_id)
                            m_student = f"{m_student_obj.encrypted_name} ({str(m_student_id)[:8]}...)"
                        except Exception:
                            m_student = f"{str(m_student_id)[:8]}..."

                    m_score = result.get("confidence_score", 0.0)
                    html.append('<tr style="background:#222;">')
                    html.append(f'<td style="padding:6px;border:1px solid #555;color:#fff;">{model_name}</td>')
                    html.append(f'<td style="padding:6px;border:1px solid #555;color:#fff;">{m_student}</td>')
                    html.append(
                        f'<td style="padding:6px;border:1px solid #555;"><span style="color:{score_color(m_score)};">{m_score:.4f}</span></td>'
                    )
                    html.append("</tr>")

                html.append("</table>")

            # Voting summary
            vote_dist = voting.get("vote_distribution", {})
            reason = voting.get("reason", "unknown").replace("_", " ").title()
            total_crops = voting.get("total_crops", 0)
            max_votes = max(vote_dist.values()) if vote_dist.values() else 0

            # Format vote_dist with student names
            vote_items = []
            for student_id, vote_count in vote_dist.items():
                try:
                    from students.models import Student

                    student_obj = Student.objects.get(student_id=student_id)
                    vote_items.append(f"{student_obj.encrypted_name}:{vote_count}")
                except Exception:
                    vote_items.append(f"{str(student_id)[:8]}...:{vote_count}")
            vote_str = ", ".join(vote_items) or "none"

            html.append('<div style="margin-top:10px;padding:8px;background:#333;border-left:4px solid #666;">')
            html.append(f'<strong style="color:#fff;">Voting:</strong> <span style="color:#fff;">{reason}</span><br/>')
            html.append(f'<small style="color:#ddd;">Result: {max_votes}/{total_crops} frames agreed | Votes: {vote_str}</small>')
            html.append("</div>")
            html.append("</div>")

            # === MATCH SUMMARY ===
            backend_student_uuid = obj.backend_student
            kiosk_uuid = obj.student.student_id if obj.student else None
            is_match = backend_student_uuid and str(backend_student_uuid) == str(kiosk_uuid)

            # Get backend student name from UUID
            backend_student_name = ""
            backend_uuid_display = ""
            if backend_student_uuid:
                try:
                    import uuid as uuid_lib

                    from students.models import Student

                    # Convert to string and extract UUID if it has prefix
                    uuid_str = str(backend_student_uuid)

                    # Strip common prefixes like "Student " that may be added
                    uuid_str = uuid_str.replace("Student ", "").strip()

                    # Try to parse as UUID to validate/clean it
                    try:
                        # If it's a valid UUID string, use it directly
                        clean_uuid = uuid_lib.UUID(uuid_str)
                        uuid_str = str(clean_uuid)
                    except (ValueError, AttributeError):
                        # If not a valid UUID, it might be a UUID object or invalid
                        # Try to get the hex attribute if it's a UUID object
                        if hasattr(backend_student_uuid, "hex"):
                            uuid_str = str(backend_student_uuid)
                        else:
                            # Last resort: use string representation
                            uuid_str = str(backend_student_uuid)

                    backend_student_obj = Student.objects.get(student_id=uuid_str)
                    backend_student_name = backend_student_obj.encrypted_name
                    backend_uuid_display = uuid_str[:8] + "..."
                except Student.DoesNotExist:
                    backend_student_name = "Unknown Student"
                    backend_uuid_display = str(backend_student_uuid)[:8] + "..."
                except Exception as e:
                    # Debug: show what we have and why it failed
                    backend_student_name = f"[Error: {type(e).__name__}]"
                    backend_uuid_display = str(backend_student_uuid)[:20]

            # Get actual models used from model_results
            models_used = list(model_results.keys()) if model_results else []
            models_display = " + ".join(models_used) if models_used else "Unknown models"

            # Format: NAME (uuid: xxx)
            kiosk_display = f"{kiosk_name} (uuid: {str(kiosk_uuid)[:8]}...)" if kiosk_name else str(kiosk_uuid)[:8] + "..."
            backend_display = (
                f"{backend_student_name} (uuid: {backend_uuid_display})"
                if backend_student_name
                else (backend_uuid_display if backend_uuid_display else "?")
            )

            if is_match:
                html.append('<div style="padding:15px;background:#d4edda;border:3px solid #28a745;border-radius:6px;">')
                html.append('<strong style="color:#155724;font-size:18px;">✅ VERIFIED MATCH</strong><br/>')
                html.append('<table style="width:100%;margin-top:10px;border-collapse:collapse;">')
                # Kiosk row
                html.append('<tr><td style="padding:6px;color:#155724;"><strong>Kiosk:</strong></td>')
                html.append(f'<td style="padding:6px;color:#155724;font-weight:bold;">{kiosk_display} @ {kiosk_score:.4f}</td></tr>')
                # Backend row
                html.append('<tr><td style="padding:6px;color:#155724;"><strong>Backend:</strong></td>')
                html.append(f'<td style="padding:6px;color:#155724;font-weight:bold;">{backend_display} @ {backend_score:.4f}</td></tr>')
                # Models row
                html.append('<tr><td style="padding:6px;color:#155724;"><strong>Models:</strong></td>')
                html.append(f'<td style="padding:6px;color:#155724;">{models_display}</td></tr>')
                html.append("</table></div>")
            else:
                html.append('<div style="padding:15px;background:#f8d7da;border:3px solid #dc3545;border-radius:6px;">')
                html.append('<strong style="color:#721c24;font-size:18px;">🔴 MISMATCH DETECTED</strong><br/>')
                html.append('<table style="width:100%;margin-top:10px;border-collapse:collapse;">')
                # Kiosk row
                html.append('<tr><td style="padding:6px;color:#721c24;"><strong>Kiosk:</strong></td>')
                html.append(f'<td style="padding:6px;color:#721c24;font-weight:bold;">{kiosk_display} @ {kiosk_score:.4f}</td></tr>')
                # Backend row
                html.append('<tr><td style="padding:6px;color:#721c24;"><strong>Backend:</strong></td>')
                html.append(f'<td style="padding:6px;color:#721c24;font-weight:bold;">{backend_display} @ {backend_score:.4f}</td></tr>')
                # Models row
                html.append('<tr><td style="padding:6px;color:#721c24;"><strong>Models:</strong></td>')
                html.append(f'<td style="padding:6px;color:#721c24;">{models_display}</td></tr>')
                html.append("</table></div>")

            return format_html("".join(html))

        except Exception as e:
            return format_html(f'<span style="color:red;">Error: {e}</span>')

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
