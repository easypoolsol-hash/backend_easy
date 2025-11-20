"""Face Verification URLs"""

from django.urls import path

from . import views

app_name = "face_verification"

urlpatterns = [
    # Cloud Tasks handler (called by Cloud Tasks service)
    path("verify/", views.verify_event_handler, name="verify_event_handler"),
    # Get verification status for an event
    path("events/<str:event_id>/", views.get_verification_status, name="get_verification_status"),
]
