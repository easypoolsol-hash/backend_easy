"""URL configuration for school dashboard."""

from django.urls import path

from . import views

app_name = "school_dashboard"

urlpatterns = [
    # Authentication
    path("login/", views.SchoolLoginView.as_view(), name="login"),
    path("logout/", views.SchoolLogoutView.as_view(), name="logout"),
    # Main dashboard
    path("", views.DashboardView.as_view(), name="dashboard"),
    # HTMX partials for auto-refresh
    path(
        "api/recent-events/",
        views.recent_events_partial,
        name="recent_events",
    ),
    path("api/bus-stats/", views.bus_stats_partial, name="bus_stats"),
    path("api/bus-locations/", views.bus_locations_api, name="bus_locations"),
]
