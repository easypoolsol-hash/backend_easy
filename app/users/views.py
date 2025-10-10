from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import APIKey, AuditLog, Role, User
from .serializers import (
    APIKeyCreateSerializer,
    APIKeySerializer,
    AuditLogSerializer,
    RoleSerializer,
    UserCreateSerializer,
    UserSerializer,
)

# pylint: disable=no-member


class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Role.objects.filter(is_active=True)
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def get_queryset(self):
        queryset = User.objects.select_related("role")
        # School admins can only see users in their school (future enhancement)
        # Parents can only see themselves (future enhancement)
        return queryset

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def me(self, request):
        """Get current authenticated user information"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], permission_classes=[])
    def login(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"error": "Username and password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(username=username, password=password)
        if user:
            refresh = RefreshToken.for_user(user)
            user.last_login = timezone.now()
            user.save(update_fields=["last_login"])

            # Log the login
            AuditLog.objects.create(
                user=user,
                action="LOGIN",
                resource_type="user",
                resource_id=str(user.user_id),
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )

            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "user": UserSerializer(user).data,
                }
            )

        return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


class APIKeyViewSet(viewsets.ModelViewSet):
    queryset = APIKey.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return APIKeyCreateSerializer
        return APIKeySerializer

    def get_queryset(self):
        return APIKey.objects.filter(is_active=True)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        api_key = self.get_object()
        api_key.is_active = False
        api_key.save()

        # Log the revocation
        AuditLog.objects.create(
            user=request.user,
            action="UPDATE",
            resource_type="api_key",
            resource_id=str(api_key.key_id),
            changes={"is_active": False},
            ip_address=self.get_client_ip(request),
        )

        return Response({"status": "API key revoked"})

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("user").order_by("-timestamp")
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by date range
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")

        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)

        # Filter by user
        user_id = self.request.query_params.get("user_id")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        # Filter by action
        action = self.request.query_params.get("action")
        if action:
            queryset = queryset.filter(action=action)

        # Filter by resource type
        resource_type = self.request.query_params.get("resource_type")
        if resource_type:
            queryset = queryset.filter(resource_type=resource_type)

        return queryset


class KioskTokenRefreshView(TokenRefreshView):
    """
    Custom TokenRefreshView that supports both regular JWT and kiosk JWT tokens.

    This ensures kiosk devices can refresh their tokens without authentication failures.
    """

    pass
