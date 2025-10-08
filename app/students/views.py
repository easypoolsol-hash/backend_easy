import time

from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from bus_kiosk_backend.permissions import IsSchoolAdmin
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
    StudentParentSerializer,
    StudentPhotoSerializer,
    StudentSerializer,
)
from .tasks import process_student_attendance

# pylint: disable=no-member


class SchoolViewSet(viewsets.ModelViewSet):
    queryset = School.objects.all()
    serializer_class = SchoolSerializer
    permission_classes = [IsSchoolAdmin]


# BusViewSet REMOVED - Use buses.views.BusViewSet instead
# The full-featured implementation is in app/buses/views.py with:
# - Bulk student assignment
# - Capacity checking
# - Utilization reports
# This duplicate was causing URL routing conflicts and confusion


class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [IsSchoolAdmin]

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

        # Search by name (fuzzy search on encrypted field -
        # limited functionality)
        search = self.request.query_params.get("search")
        if search:
            # Note: This is a basic search - in production you'd want
            # full-text search
            queryset = queryset.filter(Q(name__icontains=search) | Q(grade__icontains=search))

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
    queryset = Parent.objects.all()
    serializer_class = ParentSerializer
    permission_classes = [IsSchoolAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Search by phone or email (encrypted fields - limited search)
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(phone__icontains=search) | Q(email__icontains=search))

        return queryset

    @action(detail=True, methods=["get"])
    def students(self, request, pk=None):
        parent = self.get_object()
        student_parents = parent.student_parents.select_related("student").all()
        serializer = StudentParentSerializer(student_parents, many=True)
        return Response(serializer.data)


class StudentParentViewSet(viewsets.ModelViewSet):
    queryset = StudentParent.objects.all()
    serializer_class = StudentParentSerializer
    permission_classes = [IsSchoolAdmin]

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
    permission_classes = [IsSchoolAdmin]

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
