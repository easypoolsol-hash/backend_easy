from django import forms
from django.contrib import admin

from .models import Bus, BusStop, Route, RouteStop, RouteWaypoint, Waypoint


@admin.register(BusStop)
class BusStopAdmin(admin.ModelAdmin):
    """Admin interface for bus stops"""

    list_display = [
        "name",
        "latitude",
        "longitude",
        "is_active",
        "created_at",
    ]
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

    list_display = ["name", "is_active", "has_polyline", "stop_count", "total_students", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["route_id", "encoded_polyline", "created_at", "updated_at"]  # Make polyline readonly
    ordering = ["name"]
    inlines = [RouteStopInline]

    fieldsets = (
        ("Route Info", {"fields": ("route_id", "name", "description", "is_active")}),
        (
            "Visual Display",
            {"fields": ("color_code", "line_pattern")},
        ),
        (
            "Auto-Generated Polyline",
            {
                "fields": ("encoded_polyline",),
                "classes": ("collapse",),
                "description": "Polyline is auto-generated from waypoints. Add waypoints below to generate.",
            },
        ),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def has_polyline(self, obj):
        """Show if route has a polyline"""
        return bool(obj.encoded_polyline)

    has_polyline.boolean = True  # type: ignore[attr-defined]
    has_polyline.short_description = "Has Polyline"  # type: ignore[attr-defined]

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
        ("Bus Info", {"fields": ("bus_id", "bus_number", "license_plate", "status", "capacity")}),
        ("Assignment", {"fields": ("route", "device_id")}),
        (
            "Personnel",
            {
                "fields": (
                    ("driver_name", "driver_phone"),
                    "driver_address",
                    "driver_license_number",
                    ("conductor_name", "conductor_phone"),
                    "conductor_address",
                ),
                "classes": ("collapse",),
            },
        ),
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


@admin.register(Waypoint)
class WaypointAdmin(admin.ModelAdmin):
    """Admin interface for waypoints"""

    list_display = ["__str__", "waypoint_type", "latitude", "longitude", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["metadata__name"]
    readonly_fields = ["waypoint_id", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def waypoint_type(self, obj):
        """Show waypoint type from metadata"""
        return obj.metadata.get("type", "waypoint")

    waypoint_type.short_description = "Type"  # type: ignore[attr-defined]


class RouteWaypointInlineForm(forms.ModelForm):
    """Custom form for route waypoints with bus stop selection"""

    POINT_TYPE_CHOICES = [
        ("waypoint", "Waypoint (Path Adjustment)"),
        ("bus_stop", "Bus Stop"),
    ]

    point_type = forms.ChoiceField(
        choices=POINT_TYPE_CHOICES,
        initial="bus_stop",
        required=False,
        help_text="Select whether this is a bus stop or waypoint",
    )

    bus_stop = forms.ModelChoiceField(
        queryset=BusStop.objects.filter(is_active=True).order_by("name"),
        required=False,
        help_text="Select a bus stop (main stop)",
    )

    waypoint = forms.ModelChoiceField(
        queryset=Waypoint.objects.all().order_by("-created_at"),
        required=False,
        help_text="Select a waypoint (path adjustment)",
    )

    sequence = forms.IntegerField(
        required=True,
        widget=forms.NumberInput(attrs={"class": "auto-sequence"}),
        help_text="Auto-filled based on order (editable)",
    )

    class Meta:
        model = RouteWaypoint
        fields = ["point_type", "bus_stop", "waypoint", "sequence"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If editing existing, set point_type based on waypoint metadata
        if self.instance and self.instance.pk and self.instance.waypoint:
            if self.instance.waypoint.is_bus_stop:
                self.initial["point_type"] = "bus_stop"
                # Try to find matching bus stop
                metadata = self.instance.waypoint.metadata
                if "bus_stop_id" in metadata:
                    try:
                        bus_stop = BusStop.objects.get(stop_id=metadata["bus_stop_id"])
                        self.initial["bus_stop"] = bus_stop
                    except BusStop.DoesNotExist:
                        pass
            else:
                self.initial["point_type"] = "waypoint"

    def clean(self):
        cleaned_data = super().clean()
        point_type = cleaned_data.get("point_type")
        bus_stop = cleaned_data.get("bus_stop")
        waypoint = cleaned_data.get("waypoint")

        # Ensure either bus_stop or waypoint is selected based on type
        if point_type == "bus_stop" and not bus_stop:
            raise forms.ValidationError("Please select a bus stop when point type is 'Bus Stop'")
        elif point_type == "waypoint" and not waypoint:
            raise forms.ValidationError("Please select a waypoint when point type is 'Waypoint'")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        point_type = self.cleaned_data.get("point_type")
        bus_stop = self.cleaned_data.get("bus_stop")
        waypoint = self.cleaned_data.get("waypoint")

        if point_type == "bus_stop" and bus_stop:
            # Convert bus stop to waypoint or find existing
            waypoint_obj, _created = Waypoint.objects.get_or_create(
                latitude=bus_stop.latitude,
                longitude=bus_stop.longitude,
                metadata__type="bus_stop",
                metadata__bus_stop_id=str(bus_stop.stop_id),
                defaults={
                    "metadata": {
                        "type": "bus_stop",
                        "name": bus_stop.name,
                        "bus_stop_id": str(bus_stop.stop_id),
                    }
                },
            )
            instance.waypoint = waypoint_obj
        elif point_type == "waypoint" and waypoint:
            instance.waypoint = waypoint

        if commit:
            instance.save()

        return instance


class RouteWaypointInline(admin.TabularInline):
    """Inline for managing route waypoints"""

    model = RouteWaypoint
    form = RouteWaypointInlineForm
    extra = 1
    fields = ["point_type", "bus_stop", "waypoint", "sequence"]
    ordering = ["sequence"]
    # Use regular dropdowns, not autocomplete
    raw_id_fields = []

    class Media:
        js = ("admin/js/route_waypoint_toggle.js",)


# Add the waypoint inline to RouteAdmin
RouteAdmin.inlines = [RouteWaypointInline]
