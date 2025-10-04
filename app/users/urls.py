from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"roles", views.RoleViewSet)
router.register(r"users", views.UserViewSet)
router.register(r"api-keys", views.APIKeyViewSet)
router.register(r"audit-logs", views.AuditLogViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
