from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"schools", views.SchoolViewSet)
router.register(r"buses", views.BusViewSet)
router.register(r"students", views.StudentViewSet)
router.register(r"student-photos", views.StudentPhotoViewSet)
router.register(r"parents", views.ParentViewSet)
router.register(r"student-parents", views.StudentParentViewSet)
router.register(r"face-embeddings", views.FaceEmbeddingMetadataViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("kiosk/boarding/", views.KioskBoardingView.as_view(), name="kiosk-boarding"),
]
