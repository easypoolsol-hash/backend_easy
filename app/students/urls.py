from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"schools", views.SchoolViewSet)
router.register(r"students", views.StudentViewSet)
router.register(r"student-photos", views.StudentPhotoViewSet)
router.register(r"parents", views.ParentViewSet)
router.register(r"parents/me", views.ParentMeViewSet, basename="parent-me")
router.register(r"student-parents", views.StudentParentViewSet)
# face-embeddings endpoint removed - embeddings are generated server-side
# and packaged into kiosk snapshots. No API access needed.

urlpatterns = [
    path("", include(router.urls)),
    path("kiosk/boarding/", views.KioskBoardingView.as_view(), name="kiosk-boarding"),
    path("photos/<uuid:photo_id>/", views.serve_student_photo, name="student-photo-serve"),
]
