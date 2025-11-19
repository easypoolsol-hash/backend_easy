"""
Unit tests for Face Enrollment feature

Tests model methods, serializers, and permissions in isolation.
Uses @pytest.mark.parametrize for efficient multi-case testing.
"""

import base64

from django.contrib.auth.models import Group
import pytest
from rest_framework.test import APIRequestFactory

from bus_kiosk_backend.permissions import IsApprovedParent
from students.models import StudentPhoto
from students.serializers import (
    FaceEnrollmentStatusSerializer,
    FaceEnrollmentSubmissionSerializer,
)
from tests.factories import (
    FaceEnrollmentFactory,
    ParentFactory,
    StudentFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestFaceEnrollmentModel:
    """Tests for FaceEnrollment model methods"""

    def test_create_enrollment(self):
        """Basic enrollment creation"""
        enrollment = FaceEnrollmentFactory()
        assert enrollment.status == "pending_approval"
        assert enrollment.photo_count == 3
        assert len(enrollment.photos_data) == 3

    @pytest.mark.parametrize(
        "initial_status,expected_status",
        [
            ("pending_approval", "approved"),
        ],
    )
    def test_approve_transitions(self, initial_status, expected_status):
        """Test approve() method status transitions"""
        admin_user = UserFactory()
        enrollment = FaceEnrollmentFactory(status=initial_status)

        enrollment.approve(admin_user)

        assert enrollment.status == expected_status
        assert enrollment.reviewed_by == admin_user
        assert enrollment.reviewed_at is not None

    def test_approve_creates_student_photos(self):
        """Approve should create StudentPhoto records from enrollment photos"""
        admin_user = UserFactory()
        parent = ParentFactory()
        student = StudentFactory()
        enrollment = FaceEnrollmentFactory(
            parent=parent,
            student=student,
            photo_count=3,
        )

        initial_photo_count = StudentPhoto.objects.filter(student=student).count()

        enrollment.approve(admin_user)

        # Should create 3 new photos
        final_photo_count = StudentPhoto.objects.filter(student=student).count()
        assert final_photo_count == initial_photo_count + 3

        # Photos should be marked as submitted by parent
        new_photos = StudentPhoto.objects.filter(
            student=student,
            submitted_by_parent=parent,
        )
        assert new_photos.count() == 3

    @pytest.mark.parametrize(
        "initial_status,expected_status",
        [
            ("pending_approval", "rejected"),
        ],
    )
    def test_reject_transitions(self, initial_status, expected_status):
        """Test reject() method status transitions"""
        admin_user = UserFactory()
        enrollment = FaceEnrollmentFactory(status=initial_status)

        enrollment.reject(admin_user)

        assert enrollment.status == expected_status
        assert enrollment.reviewed_by == admin_user
        assert enrollment.reviewed_at is not None


@pytest.mark.django_db
class TestFaceEnrollmentSubmissionSerializer:
    """Tests for submission serializer validation"""

    def _create_valid_photo_base64(self):
        """Create valid base64 encoded image data"""
        fake_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100
        return base64.b64encode(fake_jpeg).decode()

    def test_valid_submission_3_photos(self):
        """Valid submission with 3 photos passes validation"""
        photos = [self._create_valid_photo_base64() for _ in range(3)]
        serializer = FaceEnrollmentSubmissionSerializer(
            data={
                "photos": photos,
                "device_info": {"app_version": "1.0.0"},
            }
        )
        assert serializer.is_valid(), serializer.errors

    def test_valid_submission_5_photos(self):
        """Valid submission with 5 photos (max) passes validation"""
        photos = [self._create_valid_photo_base64() for _ in range(5)]
        serializer = FaceEnrollmentSubmissionSerializer(
            data={
                "photos": photos,
            }
        )
        assert serializer.is_valid(), serializer.errors

    @pytest.mark.parametrize(
        "photo_count,expected_error",
        [
            (0, "at least 1"),  # ListField min_length=1
            (1, "Minimum 3 photos required"),
            (2, "Minimum 3 photos required"),
            (6, "Maximum 5 photos allowed"),
            (10, "Maximum 5 photos allowed"),
        ],
    )
    def test_invalid_photo_count(self, photo_count, expected_error):
        """Reject invalid photo counts"""
        photos = [self._create_valid_photo_base64() for _ in range(photo_count)]
        serializer = FaceEnrollmentSubmissionSerializer(
            data={
                "photos": photos,
            }
        )

        is_valid = serializer.is_valid()
        assert not is_valid
        assert expected_error in str(serializer.errors)

    def test_invalid_base64_photo(self):
        """Reject non-base64 photo data"""
        serializer = FaceEnrollmentSubmissionSerializer(
            data={
                "photos": ["not-valid-base64!!!", "also-invalid", "third-bad"],
            }
        )

        is_valid = serializer.is_valid()
        assert not is_valid
        assert "not valid base64" in str(serializer.errors)


@pytest.mark.django_db
class TestFaceEnrollmentStatusSerializer:
    """Tests for status serializer"""

    def test_serialize_pending_enrollment(self):
        """Serialize pending enrollment correctly"""
        enrollment = FaceEnrollmentFactory(status="pending_approval")
        serializer = FaceEnrollmentStatusSerializer(enrollment)
        data = serializer.data

        assert data["status"] == "pending_approval"
        assert data["photo_count"] == 3
        assert data["reviewed_at"] is None

    def test_serialize_approved_enrollment(self):
        """Serialize approved enrollment with review timestamp"""
        admin = UserFactory()
        enrollment = FaceEnrollmentFactory(status="pending_approval")
        enrollment.approve(admin)

        serializer = FaceEnrollmentStatusSerializer(enrollment)
        data = serializer.data

        assert data["status"] == "approved"
        assert data["reviewed_at"] is not None


@pytest.mark.django_db
class TestIsApprovedParentPermission:
    """Tests for IsApprovedParent permission class"""

    def _create_request(self):
        """Create a mock request"""
        factory = APIRequestFactory()
        return factory.get("/api/v1/parents/me/")

    def test_unauthenticated_denied(self):
        """Deny unauthenticated users"""
        request = self._create_request()
        request.user = None

        permission = IsApprovedParent()
        assert not permission.has_permission(request, None)

    def test_non_parent_group_denied(self):
        """Deny users not in Parent group"""
        user = UserFactory()  # Default group is Backend Engineer
        request = self._create_request()
        request.user = user

        permission = IsApprovedParent()
        assert not permission.has_permission(request, None)

    def test_parent_without_profile_denied(self):
        """Deny parent group user without Parent profile"""
        user = UserFactory()
        parent_group, _ = Group.objects.get_or_create(name="Parent")
        user.groups.clear()
        user.groups.add(parent_group)
        # No Parent profile created

        request = self._create_request()
        request.user = user

        permission = IsApprovedParent()
        assert not permission.has_permission(request, None)

    @pytest.mark.parametrize(
        "approval_status,expected_allowed",
        [
            ("pending", False),
            ("rejected", False),
            ("approved", True),
        ],
    )
    def test_approval_status_check(self, approval_status, expected_allowed):
        """Test permission based on parent approval status"""
        user = UserFactory()
        parent_group, _ = Group.objects.get_or_create(name="Parent")
        user.groups.clear()
        user.groups.add(parent_group)

        # Create parent with specific status
        ParentFactory(user=user, approval_status=approval_status)

        request = self._create_request()
        request.user = user

        permission = IsApprovedParent()
        assert permission.has_permission(request, None) == expected_allowed
