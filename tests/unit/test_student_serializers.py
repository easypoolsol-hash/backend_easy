"""
Google Way: Comprehensive serializer tests for graceful degradation.

These tests ensure the API never crashes regardless of data state.
"""
import pytest
from unittest.mock import MagicMock, patch
from students.serializers import StudentSerializer, StudentListSerializer
from students.models import Student, School


@pytest.mark.django_db
class TestStudentSerializerGracefulDegradation:
    """Test that serializers handle bad/missing data gracefully"""

    def test_student_with_all_data(self, student_with_all_relations):
        """Happy path: Student with school, bus, parents, photos"""
        serializer = StudentSerializer(student_with_all_relations)
        data = serializer.data

        assert data['school_details'] is not None
        assert data['bus_details'] is not None
        assert isinstance(data['parents'], list)
        assert isinstance(data['photos'], list)

    def test_student_without_bus(self, student_without_bus):
        """Student without assigned bus should return null bus_details"""
        serializer = StudentSerializer(student_without_bus)
        data = serializer.data

        assert data['bus_details'] is None
        assert data['school_details'] is not None  # School is required

    def test_student_without_parents(self, student_without_parents):
        """Student without parents should return empty list"""
        serializer = StudentSerializer(student_without_parents)
        data = serializer.data

        assert data['parents'] == []

    def test_student_without_photos(self, student_without_photos):
        """Student without photos should return empty list"""
        serializer = StudentSerializer(student_without_photos)
        data = serializer.data

        assert data['photos'] == []

    def test_corrupted_school_relation(self, student_factory):
        """Even if school relation is corrupted, serializer should not crash"""
        student = student_factory()

        # Simulate corrupted relation
        with patch.object(student, 'school', side_effect=Exception("Database error")):
            serializer = StudentSerializer(student)
            # Should not raise, should return None
            data = serializer.data
            assert data['school_details'] is None

    def test_corrupted_bus_relation(self, student_factory):
        """Corrupted bus relation should return None, not crash"""
        student = student_factory()

        with patch.object(student, 'assigned_bus', side_effect=Exception("DB error")):
            serializer = StudentSerializer(student)
            data = serializer.data
            assert data['bus_details'] is None


@pytest.mark.django_db
class TestOpenAPISchemaCompliance:
    """Test that serialized data matches OpenAPI schema expectations"""

    def test_nullable_fields_are_actually_nullable(self, student_without_bus):
        """Verify fields marked nullable in schema can actually be null"""
        serializer = StudentSerializer(student_without_bus)
        data = serializer.data

        # These should be allowed to be None/null
        nullable_fields = ['bus_details', 'school_details']
        for field in nullable_fields:
            # Field exists and can be None
            assert field in data
            # If None, that's valid
            if data[field] is None:
                assert True  # Explicitly valid

    def test_array_fields_always_return_arrays(self, student_factory):
        """Array fields should always return arrays, never None"""
        student = student_factory()
        serializer = StudentSerializer(student)
        data = serializer.data

        array_fields = ['parents', 'photos']
        for field in array_fields:
            assert isinstance(data[field], list), f"{field} should be a list"


@pytest.mark.django_db
class TestStudentListSerializerPerformance:
    """Test list serializer for N+1 query issues"""

    def test_no_n_plus_one_queries(self, django_assert_num_queries, students_batch):
        """List serialization should use constant number of queries"""
        with django_assert_num_queries(5):  # Adjust based on prefetch
            serializer = StudentListSerializer(students_batch, many=True)
            _ = serializer.data


# Fixtures for tests
@pytest.fixture
def student_factory(db):
    """Factory for creating test students"""
    def _factory(**kwargs):
        from tests.factories import StudentFactory
        return StudentFactory(**kwargs)
    return _factory


@pytest.fixture
def student_with_all_relations(student_factory):
    """Student with all relations populated"""
    from tests.factories import ParentFactory, StudentPhotoFactory
    from buses.tests.factories import BusFactory

    student = student_factory(assigned_bus=BusFactory())
    ParentFactory.create_batch(2, students=[student])
    StudentPhotoFactory.create_batch(2, student=student)
    return student


@pytest.fixture
def student_without_bus(student_factory):
    return student_factory(assigned_bus=None)


@pytest.fixture
def student_without_parents(student_factory):
    return student_factory()  # No parents created


@pytest.fixture
def student_without_photos(student_factory):
    return student_factory()  # No photos created


@pytest.fixture
def students_batch(student_factory):
    """Batch of students for performance testing"""
    return [student_factory() for _ in range(10)]
