from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    Bus,
    FaceEmbeddingMetadata,
    Parent,
    School,
    Student,
    StudentParent,
    StudentPhoto,
)
from .serializers import (
    BusSerializer,
    FaceEmbeddingMetadataSerializer,
    ParentSerializer,
    SchoolSerializer,
    StudentParentSerializer,
    StudentPhotoSerializer,
    StudentSerializer,
)

# pylint: disable=no-member


class SchoolViewSet(viewsets.ModelViewSet):
    queryset = School.objects.all()
    serializer_class = SchoolSerializer
    permission_classes = [IsAuthenticated]


class BusViewSet(viewsets.ModelViewSet):
    queryset = Bus.objects.all()
    serializer_class = BusSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset


class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Student.objects.select_related('school', 'assigned_bus')

        # Filter by school
        school_id = self.request.query_params.get('school_id')
        if school_id:
            queryset = queryset.filter(school_id=school_id)

        # Filter by bus
        bus_id = self.request.query_params.get('bus_id')
        if bus_id:
            queryset = queryset.filter(assigned_bus_id=bus_id)

        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by grade
        grade = self.request.query_params.get('grade')
        if grade:
            queryset = queryset.filter(grade=grade)

        # Search by name (fuzzy search on encrypted field -
        # limited functionality)
        search = self.request.query_params.get('search')
        if search:
            # Note: This is a basic search - in production you'd want
            # full-text search
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(grade__icontains=search)
            )

        return queryset

    @action(detail=True, methods=['post'])
    def assign_bus(self, request, pk=None):
        student = self.get_object()
        bus_id = request.data.get('bus_id')

        if not bus_id:
            return Response(
                {'error': 'bus_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            bus = Bus.objects.get(bus_id=bus_id, status='active')
        except Bus.DoesNotExist:
            return Response(
                {'error': 'Active bus not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        student.assigned_bus = bus
        student.save()

        return Response({
            'message': f'Student assigned to bus {bus.license_plate}',
            'student': StudentSerializer(student).data
        })

    @action(detail=True, methods=['get'])
    def parents(self, request, pk=None):
        student = self.get_object()
        student_parents = (
            student.student_parents.select_related('parent').all()
        )
        serializer = StudentParentSerializer(student_parents, many=True)
        return Response(serializer.data)


class ParentViewSet(viewsets.ModelViewSet):
    queryset = Parent.objects.all()
    serializer_class = ParentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Search by phone or email (encrypted fields - limited search)
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(phone__icontains=search) | Q(email__icontains=search)
            )

        return queryset

    @action(detail=True, methods=['get'])
    def students(self, request, pk=None):
        parent = self.get_object()
        student_parents = (
            parent.student_parents.select_related('student').all()
        )
        serializer = StudentParentSerializer(student_parents, many=True)
        return Response(serializer.data)


class StudentParentViewSet(viewsets.ModelViewSet):
    queryset = StudentParent.objects.all()
    serializer_class = StudentParentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = StudentParent.objects.select_related('student', 'parent')

        # Filter by student
        student_id = self.request.query_params.get('student_id')
        if student_id:
            queryset = queryset.filter(student_id=student_id)

        # Filter by parent
        parent_id = self.request.query_params.get('parent_id')
        if parent_id:
            queryset = queryset.filter(parent_id=parent_id)

        # Filter by relationship
        relationship = self.request.query_params.get('relationship')
        if relationship:
            queryset = queryset.filter(relationship=relationship)

        return queryset

    def create(self, request, *args, **kwargs):
        # Ensure only one primary parent per student
        if request.data.get('is_primary'):
            existing_primary = StudentParent.objects.filter(
                student_id=request.data['student'],
                is_primary=True
            )
            if existing_primary.exists():
                return Response(
                    {'error': 'Student already has a primary parent'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return super().create(request, *args, **kwargs)


class StudentPhotoViewSet(viewsets.ModelViewSet):
    queryset = StudentPhoto.objects.all()
    serializer_class = StudentPhotoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = StudentPhoto.objects.select_related('student')

        # Filter by student
        student_id = self.request.query_params.get('student_id')
        if student_id:
            queryset = queryset.filter(student_id=student_id)

        # Filter by primary photos only
        primary_only = self.request.query_params.get('primary_only')
        if primary_only and primary_only.lower() == 'true':
            queryset = queryset.filter(is_primary=True)

        return queryset

    @action(detail=True, methods=['post'])
    def set_primary(self, request, pk=None):
        photo = self.get_object()

        # Set all other photos for this student to non-primary
        StudentPhoto.objects.filter(
            student=photo.student
        ).exclude(pk=photo.pk).update(is_primary=False)

        # Set this photo as primary
        photo.is_primary = True
        photo.save()

        return Response({
            'message': 'Photo set as primary',
            'photo': StudentPhotoSerializer(photo).data
        })


class FaceEmbeddingMetadataViewSet(viewsets.ModelViewSet):
    queryset = FaceEmbeddingMetadata.objects.all()
    serializer_class = FaceEmbeddingMetadataSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = FaceEmbeddingMetadata.objects.select_related(
            'student_photo__student'
        )

        # Filter by student
        student_id = self.request.query_params.get('student_id')
        if student_id:
            queryset = queryset.filter(student_photo__student_id=student_id)

        # Filter by photo
        photo_id = self.request.query_params.get('photo_id')
        if photo_id:
            queryset = queryset.filter(student_photo_id=photo_id)

        # Filter by model name/version
        model_name = self.request.query_params.get('model_name')
        if model_name:
            queryset = queryset.filter(model_name=model_name)

        model_version = self.request.query_params.get('model_version')
        if model_version:
            queryset = queryset.filter(model_version=model_version)

        # Filter by quality score
        min_quality = self.request.query_params.get('min_quality')
        if min_quality:
            queryset = queryset.filter(quality_score__gte=float(min_quality))

        # Get only primary embeddings
        primary_only = self.request.query_params.get('primary_only')
        if primary_only and primary_only.lower() == 'true':
            queryset = queryset.filter(is_primary=True)

        return queryset

    @action(detail=True, methods=['post'])
    def set_primary(self, request, pk=None):
        embedding = self.get_object()

        # Set all other embeddings for this photo to non-primary
        FaceEmbeddingMetadata.objects.filter(
            student_photo=embedding.student_photo
        ).exclude(pk=embedding.pk).update(is_primary=False)

        # Set this embedding as primary
        embedding.is_primary = True
        embedding.save()

        return Response({
            'message': 'Face embedding set as primary',
            'embedding': FaceEmbeddingMetadataSerializer(embedding).data
        })
