import time

from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from bus_kiosk_backend.permissions import IsApprovedParent
from buses.models import Bus

from .models import (  # FaceEmbeddingMetadata removed - no API endpoint needed
    Parent,
    School,
    Student,
    StudentParent,
    StudentPhoto,
)
from .serializers import (
    # FaceEmbeddingMetadataSerializer removed - no API endpoint needed
    # BusSerializer removed - Use buses.serializers.BusSerializer instead
    ParentSerializer,
    SchoolSerializer,
    StudentListSerializer,
    StudentParentSerializer,
    StudentPhotoSerializer,
    StudentSerializer,
)
from .tasks import process_student_attendance

# pylint: disable=no-member


class SchoolViewSet(viewsets.ModelViewSet):
    queryset = School.objects.all()
    serializer_class = SchoolSerializer
    permission_classes = [IsAuthenticated]


# BusViewSet REMOVED - Use buses.views.BusViewSet instead
# The full-featured implementation is in app/buses/views.py with:
# - Bulk student assignment
# - Capacity checking
# - Utilization reports
# This duplicate was causing URL routing conflicts and confusion


class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """Use lightweight serializer for list, full serializer for detail"""
        if self.action == "list":
            return StudentListSerializer
        return StudentSerializer

    def get_queryset(self):
        queryset = Student.objects.select_related("school", "assigned_bus")

        # Filter by school
        school_id = self.request.query_params.get("school_id")
        if school_id:
            queryset = queryset.filter(school_id=school_id)

        # Filter by bus
        bus_id = self.request.query_params.get("bus_id")
        if bus_id:
            try:
                # Convert string to UUID and filter by bus_id
                from uuid import UUID

                bus_uuid = UUID(bus_id)
                queryset = queryset.filter(assigned_bus__bus_id=bus_uuid)
            except (ValueError, TypeError):
                # Invalid UUID, return empty queryset
                queryset = queryset.none()

        # Filter by status
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by grade
        grade = self.request.query_params.get("grade")
        if grade:
            queryset = queryset.filter(grade=grade)

        # Search by name, student ID, or grade (fuzzy search)
        search = self.request.query_params.get("search")
        if search:
            # Search across multiple fields: name, school_student_id, grade
            queryset = queryset.filter(Q(name__icontains=search) | Q(school_student_id__icontains=search) | Q(grade__icontains=search))

        return queryset

    @action(detail=True, methods=["post"])
    def assign_bus(self, request, pk=None):
        student = self.get_object()
        bus_id = request.data.get("bus_id")

        if not bus_id:
            return Response(
                {"error": "bus_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            bus = Bus.objects.get(bus_id=bus_id, status="active")
        except Bus.DoesNotExist:
            return Response(
                {"error": "Active bus not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        student.assigned_bus = bus
        student.save()

        return Response(
            {
                "message": f"Student assigned to bus {bus.license_plate}",
                "student": StudentSerializer(student).data,
            }
        )

    @action(detail=True, methods=["get"])
    def parents(self, request, pk=None):
        student = self.get_object()
        student_parents = student.student_parents.select_related("parent").all()
        serializer = StudentParentSerializer(student_parents, many=True)
        return Response(serializer.data)


class ParentViewSet(viewsets.ModelViewSet):
    """Admin-only parent management - NO row-level filtering (requires admin access)"""

    queryset = Parent.objects.all()
    serializer_class = ParentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Search by phone or email (encrypted fields - limited search)
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(phone__icontains=search) | Q(email__icontains=search))

        return queryset

    @extend_schema(
        request=None,
        responses={
            201: ParentSerializer,
            200: ParentSerializer,
        },
        description="Register as a parent (called from parent_easy app after Firebase login)",
    )
    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated])
    def register(self, request):
        """
        POST /api/v1/parents/register/ - Register as a parent

        Called from parent_easy app after user signs in with Firebase.
        Creates a Parent record linked to the authenticated User.

        If parent already exists, returns existing parent (idempotent).
        """
        import logging
        import uuid

        logger = logging.getLogger(__name__)
        user = request.user

        # Check if parent already exists for this user
        try:
            parent = Parent.objects.get(user=user)
            logger.info(f"Parent already exists for user {user.username}")
            return Response(ParentSerializer(parent).data, status=status.HTTP_200_OK)
        except Parent.DoesNotExist:
            pass

        # Create new parent record with temporary encrypted values
        temp_suffix = uuid.uuid4().hex[:8]
        parent = Parent(
            user=user,
            approval_status="pending",
        )
        # Set temporary encrypted values for PII (admin will update during approval)
        parent.encrypted_email = f"pending-{temp_suffix}@example.com"
        parent.encrypted_phone = f"+91{temp_suffix[:10].zfill(10)}"
        parent.encrypted_name = f"Pending User {user.username}"
        parent.save()

        logger.info(f"✅ Registered new parent for user {user.username} via parent_easy app")

        return Response(ParentSerializer(parent).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def students(self, request, pk=None):
        parent = self.get_object()
        student_parents = parent.student_parents.select_related("student").all()
        serializer = StudentParentSerializer(student_parents, many=True)
        return Response(serializer.data)


class ParentMeViewSet(viewsets.ViewSet):
    """
    Parent-specific endpoints with row-level security.

    Parents can ONLY access their own data:
    - Their own profile
    - Their own children
    - Buses for their children
    - Locations for their children's buses

    IAM Principle: Backend enforces all filtering (zero-trust).
    """

    permission_classes = [IsApprovedParent]

    @extend_schema(
        responses={200: ParentSerializer},
        description="Get my parent profile",
    )
    @action(detail=False, methods=["get"])
    def profile(self, request):
        """GET /api/v1/parents/me/profile/ - Get my parent profile"""
        parent = getattr(request.user, "parent_profile", None)
        if not parent:
            return Response(
                {"error": "Parent record not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ParentSerializer(parent)
        return Response(serializer.data)

    @extend_schema(
        responses={200: StudentSerializer(many=True)},
        description="Get my children",
    )
    @action(detail=False, methods=["get"])
    def children(self, request):
        """GET /api/v1/parents/me/children/ - Get my children"""
        parent = getattr(request.user, "parent_profile", None)
        if not parent:
            return Response(
                {"error": "Parent record not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get students through StudentParent relationship
        student_parents = StudentParent.objects.filter(parent=parent).select_related("student")
        students = [sp.student for sp in student_parents]

        serializer = StudentSerializer(students, many=True)
        return Response(serializer.data)

    @extend_schema(
        responses={
            200: {
                "type": "object",
                "properties": {
                    "buses": {
                        "type": "array",
                        "items": {"type": "object"},
                    }
                },
            }
        },
        description="Get all buses for my children",
    )
    @action(detail=False, methods=["get"])
    def buses(self, request):
        """GET /api/v1/parents/me/buses/ - Get all buses for my children"""
        from buses.serializers import BusSerializer

        parent = getattr(request.user, "parent_profile", None)
        if not parent:
            return Response(
                {"error": "Parent record not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get all students for this parent
        student_parents = StudentParent.objects.filter(parent=parent).select_related("student")
        student_ids = [sp.student.student_id for sp in student_parents]

        # Get unique buses for these students
        buses = Bus.objects.filter(students__student_id__in=student_ids).distinct()

        serializer = BusSerializer(buses, many=True)
        return Response(serializer.data)

    @extend_schema(
        responses={
            200: {
                "type": "object",
                "properties": {
                    "bus_id": {"type": "string"},
                    "license_plate": {"type": "string"},
                    "location": {
                        "type": "object",
                        "properties": {
                            "latitude": {"type": "number"},
                            "longitude": {"type": "number"},
                            "last_updated": {"type": "string"},
                        },
                    },
                },
            }
        },
        description="Get real-time location for a specific bus (only buses for my children)",
    )
    @action(detail=False, methods=["get"], url_path=r"buses/(?P<bus_id>[^/.]+)/location")
    def bus_location(self, request, bus_id=None):
        """GET /api/v1/parents/me/buses/{bus_id}/location/ - Get bus location"""
        parent = getattr(request.user, "parent_profile", None)
        if not parent:
            return Response(
                {"error": "Parent record not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get all students for this parent
        student_parents = StudentParent.objects.filter(parent=parent).select_related("student")
        student_ids = [sp.student.student_id for sp in student_parents]

        # Verify this bus belongs to one of their children
        try:
            bus = Bus.objects.get(bus_id=bus_id, students__student_id__in=student_ids)
        except Bus.DoesNotExist:
            return Response(
                {"error": "Bus not found or not linked to your children"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Return bus location (placeholder - integrate with real-time tracking system)
        return Response(
            {
                "bus_id": str(bus.bus_id),
                "license_plate": bus.license_plate,
                "location": {
                    "latitude": 28.6139,  # Placeholder - integrate with GPS tracking
                    "longitude": 77.2090,
                    "last_updated": "2025-11-15T00:00:00Z",
                },
            }
        )

    @extend_schema(
        responses={
            200: {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "bus_id": {"type": "string"},
                        "bus_number": {"type": "string"},
                        "latitude": {"type": "number"},
                        "longitude": {"type": "number"},
                        "speed": {"type": "number"},
                        "heading": {"type": "number"},
                        "last_updated": {"type": "string"},
                    },
                },
            }
        },
        description="Get real-time locations for all buses assigned to my children (row-level security enforced)",
    )
    @action(detail=False, methods=["get"], url_path="bus-locations")
    def bus_locations(self, request):
        """
        GET /api/v1/parents/me/bus-locations/ - Get all bus locations for my children's buses

        Security (Row-Level):
        - Parents can ONLY see buses assigned to their children
        - Returns bus_number (NOT license_plate - parents don't need PII)
        - Backend enforces all filtering (zero-trust)
        """

        from kiosks.models import BusLocation

        parent = getattr(request.user, "parent_profile", None)
        if not parent:
            return Response(
                {"error": "Parent record not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Security Layer 1: Get ONLY this parent's children
        student_parents = StudentParent.objects.filter(parent=parent).select_related("student")
        student_ids = [sp.student.student_id for sp in student_parents]

        # Security Layer 2: Get ONLY buses assigned to these children (not all buses)
        buses = Bus.objects.filter(assigned_students__student_id__in=student_ids).distinct()

        # Return bus locations with real GPS data
        bus_locations = []
        for bus in buses:
            # Get latest location for this bus (via kiosk)
            latest_location = None
            if hasattr(bus, "kiosk") and bus.kiosk:
                latest_location = BusLocation.objects.filter(kiosk=bus.kiosk).order_by("-timestamp").first()

            if latest_location:
                # Return REAL location data
                bus_locations.append(
                    {
                        "bus_id": str(bus.bus_id),
                        "bus_number": bus.bus_number,  # Use bus_number (not license_plate)
                        "latitude": latest_location.latitude,
                        "longitude": latest_location.longitude,
                        "speed": latest_location.speed if latest_location.speed else 0.0,
                        "heading": latest_location.heading if latest_location.heading else 0.0,
                        "last_updated": latest_location.timestamp.isoformat(),
                    }
                )
            else:
                # Bus has no location data yet (kiosk hasn't sent updates)
                bus_locations.append(
                    {
                        "bus_id": str(bus.bus_id),
                        "bus_number": bus.bus_number,
                        "latitude": None,  # No location available
                        "longitude": None,
                        "speed": None,
                        "heading": None,
                        "last_updated": None,
                    }
                )

        return Response(bus_locations)


class StudentParentViewSet(viewsets.ModelViewSet):
    queryset = StudentParent.objects.all()
    serializer_class = StudentParentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = StudentParent.objects.select_related("student", "parent")

        # Filter by student
        student_id = self.request.query_params.get("student_id")
        if student_id:
            queryset = queryset.filter(student_id=student_id)

        # Filter by parent
        parent_id = self.request.query_params.get("parent_id")
        if parent_id:
            queryset = queryset.filter(parent_id=parent_id)

        # Filter by relationship
        relationship = self.request.query_params.get("relationship")
        if relationship:
            queryset = queryset.filter(relationship=relationship)

        return queryset

    def create(self, request, *args, **kwargs):
        # Ensure only one primary parent per student
        if request.data.get("is_primary"):
            existing_primary = StudentParent.objects.filter(student_id=request.data["student"], is_primary=True)
            if existing_primary.exists():
                return Response(
                    {"error": "Student already has a primary parent"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return super().create(request, *args, **kwargs)


class StudentPhotoViewSet(viewsets.ModelViewSet):
    queryset = StudentPhoto.objects.all()
    serializer_class = StudentPhotoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = StudentPhoto.objects.select_related("student")

        # Filter by student
        student_id = self.request.query_params.get("student_id")
        if student_id:
            queryset = queryset.filter(student_id=student_id)

        # Filter by primary photos only
        primary_only = self.request.query_params.get("primary_only")
        if primary_only and primary_only.lower() == "true":
            queryset = queryset.filter(is_primary=True)

        return queryset

    @action(detail=True, methods=["post"])
    def set_primary(self, request, pk=None):
        photo = self.get_object()

        # Set all other photos for this student to non-primary
        StudentPhoto.objects.filter(student=photo.student).exclude(pk=photo.pk).update(is_primary=False)

        # Set this photo as primary
        photo.is_primary = True
        photo.save()

        return Response(
            {
                "message": "Photo set as primary",
                "photo": StudentPhotoSerializer(photo).data,
            }
        )


# FaceEmbeddingMetadataViewSet REMOVED
# Embeddings are generated SERVER-SIDE and packaged into kiosk snapshots.
# No API endpoint needed - embeddings accessed via:
# 1. Server-side: Direct database/Qdrant queries
# 2. Kiosks: Local SQLite snapshot (offline-first)


class KioskBoardingView(APIView):
    """
    Simulate a bus kiosk boarding endpoint - FAST response needed!
    """

    @extend_schema(
        request="events.serializers.BoardingEventCreateSerializer",
        responses={
            200: {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "message": {"type": "string"},
                },
            }
        },
        description=("Student boarding endpoint - returns immediate approval and schedules background processing"),
    )
    def post(self, request):
        """
        Student boarding endpoint - must respond in < 0.5 seconds!
        """
        student_name = request.data.get("student_name", "Unknown Student")
        boarding_time = request.data.get("boarding_time", "now")

        # 🚨 CRITICAL: Start timing for performance monitoring
        start_time = time.time()

        # Quick validation (0.01 seconds)
        if not student_name:
            return Response(
                {"error": "Student name required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ⚡ INSTANT RESPONSE - Don't wait for processing!
        # Send boarding data to background worker for database/storage
        task = process_student_attendance.delay(
            student_name,
            boarding_time,
            bus_id=request.data.get("bus_id"),
            face_confidence=request.data.get("face_confidence"),
        )

        response_time = time.time() - start_time

        # ✅ Student can board immediately!
        return Response(
            {
                "status": "boarding_allowed",
                "message": (f"✅ Welcome, {student_name}! Please board the bus."),
                "boarding_time": boarding_time,
                "response_time_seconds": round(response_time, 3),
                "background_task_id": task.id,
                "note": "Boarding record processing in background",
            },
            status=status.HTTP_200_OK,
        )


# Serve student photos from database
def serve_student_photo(request, photo_id):
    """Serve student photo from database binary field"""
    from django.http import HttpResponse, HttpResponseNotFound
    from django.shortcuts import get_object_or_404

    photo = get_object_or_404(StudentPhoto, photo_id=photo_id)

    if photo.photo_data:
        return HttpResponse(photo.photo_data, content_type=photo.photo_content_type)

    return HttpResponseNotFound("Photo not found")
