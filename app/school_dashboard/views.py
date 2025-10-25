"""Views for school dashboard."""

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from buses.models import Bus
from events.models import BoardingEvent


class SchoolLoginView(View):
    """Custom login view for school dashboard users."""

    template_name = "school_dashboard/login.html"

    def get(self, request):
        """Display login form."""
        # If already logged in with correct role, redirect to dashboard
        if request.user.is_authenticated:
            if hasattr(request.user, "is_school_admin") and (request.user.is_school_admin or request.user.is_super_admin):
                return redirect("school_dashboard:dashboard")

        return render(request, self.template_name)

    def post(self, request):
        """Handle login submission."""
        username = request.POST.get("username")
        password = request.POST.get("password")

        # Authenticate user
        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Check if user has school_admin or super_admin role
            if hasattr(user, "is_school_admin") and (user.is_school_admin or user.is_super_admin):
                login(request, user)
                return redirect("school_dashboard:dashboard")
            else:
                # User exists but doesn't have correct role
                return render(
                    request,
                    self.template_name,
                    {"error_message": "Access Denied: You need 'School Administrator' role to access this dashboard."},
                )
        else:
            # Invalid credentials
            return render(
                request,
                self.template_name,
                {"error_message": "Invalid username or password."},
            )


class SchoolLogoutView(View):
    """Logout view for school dashboard."""

    def get(self, request):
        """Handle logout via GET."""
        logout(request)
        return redirect("school_dashboard:login")

    def post(self, request):
        """Handle logout via POST."""
        logout(request)
        return redirect("school_dashboard:login")


class SchoolRoleRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure user has school_admin or super_admin role."""

    login_url = "/school/login/"

    def test_func(self):
        """Check if user has required role."""
        if not hasattr(self.request, "user") or not self.request.user.is_authenticated:
            return False

        # Check if user has school_admin or super_admin role
        return hasattr(self.request.user, "is_school_admin") and (self.request.user.is_school_admin or self.request.user.is_super_admin)


class DashboardView(SchoolRoleRequiredMixin, TemplateView):
    """Main school dashboard view."""

    template_name = "school_dashboard/dashboard.html"

    def get_context_data(self, **kwargs):
        """Get dashboard context data."""
        context = super().get_context_data(**kwargs)

        # Today's date for filtering
        today = timezone.now().date()

        # Bus statistics
        buses_queryset = Bus.objects.all()
        context["total_buses"] = buses_queryset.count()
        context["buses_active"] = buses_queryset.filter(status="active").count()

        # Boarding events today
        today_events = BoardingEvent.objects.filter(timestamp__date=today).select_related("student")

        context["students_boarded_today"] = today_events.count()
        context["students_unique_today"] = today_events.values("student").distinct().count()

        # Recent events (last 20)
        context["recent_events"] = BoardingEvent.objects.select_related("student").order_by("-timestamp")[:20]

        # Calculate on-time percentage (simple: events within school hours)
        school_start = timezone.now().replace(hour=7, minute=0, second=0)
        school_end = timezone.now().replace(hour=9, minute=0, second=0)

        on_time_events = today_events.filter(timestamp__gte=school_start, timestamp__lte=school_end).count()

        if context["students_boarded_today"] > 0:
            context["on_time_percentage"] = round(
                (on_time_events / context["students_boarded_today"]) * 100,
                1,
            )
        else:
            context["on_time_percentage"] = 0

        # Google Maps API key
        context["google_maps_api_key"] = settings.GOOGLE_MAPS_API_KEY

        return context


def recent_events_partial(request):
    """HTMX partial for auto-refreshing recent events."""
    # Check authentication and role
    if not request.user.is_authenticated:
        return HttpResponseForbidden("Authentication required")

    if not (hasattr(request.user, "is_school_admin") and (request.user.is_school_admin or request.user.is_super_admin)):
        return HttpResponseForbidden("Access denied")

    recent_events = BoardingEvent.objects.select_related("student").order_by("-timestamp")[:20]

    return render(
        request,
        "school_dashboard/partials/recent_events.html",
        {"recent_events": recent_events},
    )


def bus_stats_partial(request):
    """HTMX partial for auto-refreshing bus statistics."""
    # Check authentication and role
    if not request.user.is_authenticated:
        return HttpResponseForbidden("Authentication required")

    if not (hasattr(request.user, "is_school_admin") and (request.user.is_school_admin or request.user.is_super_admin)):
        return HttpResponseForbidden("Access denied")

    today = timezone.now().date()

    buses_queryset = Bus.objects.all()
    total_buses = buses_queryset.count()
    buses_active = buses_queryset.filter(status="active").count()

    today_events = BoardingEvent.objects.filter(timestamp__date=today)
    students_boarded_today = today_events.count()

    return render(
        request,
        "school_dashboard/partials/bus_stats.html",
        {
            "total_buses": total_buses,
            "buses_active": buses_active,
            "students_boarded_today": students_boarded_today,
        },
    )


@extend_schema(
    responses={
        200: inline_serializer(
            name="BusLocationsGeoJSONResponse",
            fields={
                "type": serializers.CharField(default="FeatureCollection"),
                "features": serializers.ListField(child=serializers.DictField(), help_text="GeoJSON features array"),
            },
        ),
        403: {"description": "Access denied - not school_admin or super_admin"},
    },
    operation_id="school_bus_locations_list",
    description="""
    **Fortune 500 IAM-style School Bus Locations (Admin Only)**

    Returns real-time bus locations for ALL buses in the fleet.

    **Authorization:**
    - Requires authentication (JWT token)
    - Requires role: school_admin OR super_admin
    - Returns ALL bus locations (full visibility for admins)

    **For Parents:**
    Parents should use `/api/v1/users/parent/my-buses/` instead (filtered by child assignment)

    **Response:**
    GeoJSON FeatureCollection with bus location points including:
    - Real-time GPS coordinates
    - Bus status, speed, heading
    - Last update timestamp
    """,
    tags=["School Dashboard"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def bus_locations_api(request):
    """
    Bus locations API for school dashboard (admin only).

    Fortune 500 IAM-style authorization:
    - Deny by default
    - Explicit grant for school_admin and super_admin ONLY
    - Returns ALL bus locations (full visibility for admins)

    Parents use /api/v1/users/parent/my-buses/ endpoint instead (filtered by child assignment)
    """
    # IAM-style explicit permission: ONLY school_admin and super_admin
    if not (hasattr(request.user, "is_school_admin") and (request.user.is_school_admin or request.user.is_super_admin)):
        return JsonResponse(
            {
                "error": "Access denied - insufficient permissions",
                "required_role": ["school_admin", "super_admin"],
                "your_role": request.user.role.name if hasattr(request.user, "role") else None,
            },
            status=403,
        )

    # Get latest GPS location for each bus
    from django.db.models import Max

    from kiosks.models import BusLocation

    latest_locations = BusLocation.objects.values("kiosk_id").annotate(latest_timestamp=Max("timestamp"))

    bus_locations = []
    for loc_data in latest_locations:
        location = (
            BusLocation.objects.filter(kiosk_id=loc_data["kiosk_id"], timestamp=loc_data["latest_timestamp"]).select_related("kiosk__bus").first()
        )

        if location:
            kiosk = location.kiosk
            if kiosk.bus:
                bus_name = kiosk.bus.license_plate
                bus_status = kiosk.bus.get_status_display()
            else:
                bus_name = f"Kiosk {kiosk.kiosk_id}"
                bus_status = "Unassigned"

            bus_locations.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [location.longitude, location.latitude]},
                    "properties": {
                        "id": kiosk.kiosk_id,  # Frontend expects "id"
                        "name": bus_name,  # Frontend expects "name"
                        "status": bus_status,
                        "kiosk_id": kiosk.kiosk_id,
                        "bus_name": bus_name,
                        "last_update": location.timestamp.isoformat(),
                        "speed": location.speed,
                        "heading": location.heading,
                    },
                }
            )

    return JsonResponse({"type": "FeatureCollection", "features": bus_locations})
