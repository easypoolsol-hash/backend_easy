from django.contrib import admin

from .models import Bus, BusStop, Route, RouteStop


@admin.register(BusStop)
class BusStopAdmin(admin.ModelAdmin):
    """Admin interface for bus stops"""

    list_display = ["name", "latitude", "longitude", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name"]
    readonly_fields = ["stop_id", "created_at", "updated_at"]
    ordering = ["name"]


class RouteStopInline(admin.TabularInline):
    """Inline for managing route stops"""

    model = RouteStop
    extra = 1
    fields = ["bus_stop", "sequence", "waypoints"]
    ordering = ["sequence"]


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    """Admin interface for bus routes"""

    list_display = ["name", "is_active", "stop_count", "total_students", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["route_id", "created_at", "updated_at"]
    ordering = ["name"]
    inlines = [RouteStopInline]

    fieldsets = (
        ("Route Info", {"fields": ("route_id", "name", "description", "is_active")}),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request):
        """Optimize queryset with annotations"""
        return super().get_queryset(request).prefetch_related("buses")


@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    """Admin interface for buses"""

    list_display = [
        "bus_number",
        "license_plate",
        "route",
        "status",
        "capacity",
        "assigned_students_count",
        "utilization_percentage",
        "device_id",
        "last_maintenance",
    ]
    list_filter = ["status", "route", "manufacturer", "year", "last_maintenance"]
    search_fields = ["bus_number", "license_plate", "device_id", "manufacturer", "model"]
    readonly_fields = ["bus_id", "created_at", "updated_at"]
    ordering = ["bus_number"]

    fieldsets = (
        ("Bus Info", {"fields": ("bus_id", "bus_number", "license_plate", "status")}),
        ("Assignment", {"fields": ("route", "device_id")}),
        ("Capacity", {"fields": ("capacity",)}),
        (
            "Vehicle Details",
            {
                "fields": ("manufacturer", "model", "year", "last_maintenance"),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def utilization_percentage(self, obj):
        """Display utilization as percentage"""
        return f"{obj.utilization_percentage:.1f}%"

    utilization_percentage.short_description = "Utilization"  # type: ignore[attr-defined]

    def get_queryset(self, request):
        """Optimize queryset with annotations"""
        return super().get_queryset(request).select_related("route").prefetch_related("assigned_students")
