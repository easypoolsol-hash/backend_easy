from django.contrib import admin

from notifications.models import FCMToken, Notification, NotificationPreference


@admin.register(FCMToken)
class FCMTokenAdmin(admin.ModelAdmin):
    list_display = ["parent", "platform", "is_active", "created_at", "updated_at"]
    list_filter = ["platform", "is_active", "created_at"]
    search_fields = ["parent__user__email", "token"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        "parent",
        "boarding",
        "deboarding",
        "eta",
        "announcements",
        "quiet_hours_enabled",
    ]
    list_filter = ["boarding", "deboarding", "eta", "announcements", "quiet_hours_enabled"]
    search_fields = ["parent__user__email"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        "notification_id",
        "parent",
        "notification_type",
        "title",
        "status",
        "created_at",
        "sent_at",
    ]
    list_filter = ["notification_type", "status", "created_at"]
    search_fields = ["parent__user__email", "title", "body"]
    readonly_fields = [
        "notification_id",
        "created_at",
        "queued_at",
        "sent_at",
        "read_at",
    ]
    date_hierarchy = "created_at"

    fieldsets = (
        ("Basic Info", {"fields": ("notification_id", "parent", "student", "notification_type")}),
        ("Content", {"fields": ("title", "body", "data")}),
        ("Status", {"fields": ("status", "retry_count", "error_message")}),
        ("Timestamps", {"fields": ("created_at", "queued_at", "sent_at", "read_at"), "classes": ("collapse",)}),
    )
