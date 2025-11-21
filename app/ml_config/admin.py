"""
ML Configuration Admin Interface
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import BackendModelConfiguration


@admin.register(BackendModelConfiguration)
class BackendModelConfigurationAdmin(admin.ModelAdmin):
    """
    Admin interface for backend face recognition model configuration.
    Allows tuning ML parameters dynamically without code deployment.
    """

    list_display = [
        "version_display",
        "name",
        "is_active_display",
        "weights_summary",
        "consensus_summary",
        "created_at",
    ]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "description"]
    ordering = ["-version"]

    # Read-only fields (auto-managed)
    readonly_fields = ["version", "created_at", "updated_at", "config_preview"]

    fieldsets = (
        (
            "📋 Configuration Info",
            {
                "fields": (
                    "version",
                    "name",
                    "description",
                    "is_active",
                    "created_at",
                    "updated_at",
                )
            },
        ),
        (
            "⚖️ Model Weights (must sum to 1.0)",
            {
                "fields": (
                    "mobilefacenet_weight",
                    "arcface_weight",
                    "adaface_weight",
                ),
                "description": "Weight each model's contribution to the final decision. Higher weight = more influence.",
            },
        ),
        (
            "🎯 Per-Model Thresholds",
            {
                "fields": (
                    "mobilefacenet_threshold",
                    "arcface_threshold",
                    "adaface_threshold",
                ),
                "description": "Minimum similarity score for each model to consider a match (0.0 - 1.0).",
            },
        ),
        (
            "📊 Combined Score Thresholds",
            {
                "fields": (
                    "high_confidence_threshold",
                    "medium_confidence_threshold",
                    "match_threshold",
                ),
                "description": "Combined weighted score thresholds for final decision: HIGH >= 0.55, MEDIUM >= 0.40, MATCH >= 0.35",
            },
        ),
        (
            "🗳️ Consensus Strategy",
            {
                "fields": (
                    "minimum_consensus",
                    "require_all_agree",
                    "use_weighted_vote",
                ),
                "description": "How models vote: minimum agreeing models, require unanimous decision, use weighted votes.",
            },
        ),
        (
            "🌡️ Temperature Scaling - MobileFaceNet",
            {
                "classes": ("collapse",),
                "fields": (
                    "mobilefacenet_temperature_enabled",
                    "mobilefacenet_temperature",
                    "mobilefacenet_shift",
                ),
                "description": "Adjust MobileFaceNet score distribution. Usually not needed (scores already well-distributed).",
            },
        ),
        (
            "🌡️ Temperature Scaling - ArcFace",
            {
                "classes": ("collapse",),
                "fields": (
                    "arcface_temperature_enabled",
                    "arcface_temperature",
                    "arcface_shift",
                ),
                "description": "Adjust ArcFace score distribution. RECOMMENDED: Enabled with temp=3.0, shift=-0.15 (ArcFace scores are compressed).",
            },
        ),
        (
            "🌡️ Temperature Scaling - AdaFace",
            {
                "classes": ("collapse",),
                "fields": (
                    "adaface_temperature_enabled",
                    "adaface_temperature",
                    "adaface_shift",
                ),
                "description": "Adjust AdaFace score distribution. Usually not needed (scores already well-distributed).",
            },
        ),
        (
            "🔍 Configuration Preview",
            {
                "classes": ("collapse",),
                "fields": ("config_preview",),
                "description": "JSON preview of configuration as used by consensus_service.",
            },
        ),
    )

    def version_display(self, obj):
        """Display version with badge"""
        return format_html('<span style="font-weight:bold;">V{}</span>', obj.version)

    version_display.short_description = "Version"  # type: ignore[attr-defined]

    def is_active_display(self, obj):
        """Display active status with color indicator"""
        if obj.is_active:
            return format_html('<span style="color:#28a745;font-weight:bold;">🟢 ACTIVE</span>')
        return format_html('<span style="color:#6c757d;">⚪ Inactive</span>')

    is_active_display.short_description = "Status"  # type: ignore[attr-defined]

    def weights_summary(self, obj):
        """Display model weights summary"""
        return format_html(
            "MFN: {:.2f} | ARC: {:.2f} | ADA: {:.2f}",
            obj.mobilefacenet_weight,
            obj.arcface_weight,
            obj.adaface_weight,
        )

    weights_summary.short_description = "Model Weights"  # type: ignore[attr-defined]

    def consensus_summary(self, obj):
        """Display consensus strategy summary"""
        strategy = "All agree" if obj.require_all_agree else f"≥{obj.minimum_consensus} models"
        weighted = "Weighted" if obj.use_weighted_vote else "Equal"
        return f"{strategy} ({weighted})"

    consensus_summary.short_description = "Consensus"  # type: ignore[attr-defined]

    def config_preview(self, obj):
        """Display JSON preview of configuration"""
        if not obj.pk:
            return "Save to see preview"

        import json

        config_dict = obj.to_dict()
        config_json = json.dumps(config_dict, indent=2)
        return format_html("<pre>{}</pre>", config_json)

    config_preview.short_description = "Config as JSON"  # type: ignore[attr-defined]

    def save_model(self, request, obj, form, change):
        """Save model with additional logging"""
        is_new = not obj.pk
        super().save_model(request, obj, form, change)

        if is_new:
            self.message_user(
                request,
                f"✅ Created configuration V{obj.version}: {obj.name}",
            )
        else:
            self.message_user(
                request,
                f"✅ Updated configuration V{obj.version}: {obj.name}",
            )

        if obj.is_active:
            self.message_user(
                request,
                f"🟢 Configuration V{obj.version} is now ACTIVE and will be used for all NEW boarding events.",
                level="WARNING",
            )

    actions = ["activate_configuration", "deactivate_configuration", "duplicate_configuration"]

    def activate_configuration(self, request, queryset):
        """Activate selected configuration (only one can be active)"""
        if queryset.count() > 1:
            self.message_user(
                request,
                "❌ Can only activate one configuration at a time.",
                level="ERROR",
            )
            return

        config = queryset.first()
        # Deactivate all others
        BackendModelConfiguration.objects.filter(is_active=True).update(is_active=False)
        # Activate this one
        config.is_active = True
        config.save()

        self.message_user(
            request,
            f"🟢 Activated configuration V{config.version}: {config.name}. Will be used for NEW boarding events.",
            level="SUCCESS",
        )

    activate_configuration.short_description = "🟢 Activate selected configuration"  # type: ignore[attr-defined]

    def deactivate_configuration(self, request, queryset):
        """Deactivate selected configurations"""
        count = queryset.update(is_active=False)
        self.message_user(
            request,
            f"⚪ Deactivated {count} configuration(s). ⚠️ WARNING: No active config! Will use default.",
            level="WARNING",
        )

    deactivate_configuration.short_description = "⚪ Deactivate selected configuration(s)"  # type: ignore[attr-defined]

    def duplicate_configuration(self, request, queryset):
        """Duplicate configuration for testing/tuning"""
        if queryset.count() > 1:
            self.message_user(
                request,
                "❌ Can only duplicate one configuration at a time.",
                level="ERROR",
            )
            return

        original = queryset.first()

        # Create duplicate
        duplicate = BackendModelConfiguration.objects.create(
            name=f"{original.name} (Copy)",
            description=f"Duplicated from V{original.version}",
            is_active=False,  # Duplicates start inactive
            # Copy all weights
            mobilefacenet_weight=original.mobilefacenet_weight,
            arcface_weight=original.arcface_weight,
            adaface_weight=original.adaface_weight,
            # Copy thresholds
            mobilefacenet_threshold=original.mobilefacenet_threshold,
            arcface_threshold=original.arcface_threshold,
            adaface_threshold=original.adaface_threshold,
            high_confidence_threshold=original.high_confidence_threshold,
            medium_confidence_threshold=original.medium_confidence_threshold,
            match_threshold=original.match_threshold,
            # Copy consensus
            minimum_consensus=original.minimum_consensus,
            require_all_agree=original.require_all_agree,
            use_weighted_vote=original.use_weighted_vote,
            # Copy temperature scaling
            mobilefacenet_temperature_enabled=original.mobilefacenet_temperature_enabled,
            mobilefacenet_temperature=original.mobilefacenet_temperature,
            mobilefacenet_shift=original.mobilefacenet_shift,
            arcface_temperature_enabled=original.arcface_temperature_enabled,
            arcface_temperature=original.arcface_temperature,
            arcface_shift=original.arcface_shift,
            adaface_temperature_enabled=original.adaface_temperature_enabled,
            adaface_temperature=original.adaface_temperature,
            adaface_shift=original.adaface_shift,
        )

        self.message_user(
            request,
            f"✅ Created duplicate V{duplicate.version}: {duplicate.name} (Inactive). Edit and activate when ready.",
            level="SUCCESS",
        )

    duplicate_configuration.short_description = "📋 Duplicate selected configuration"  # type: ignore[attr-defined]
