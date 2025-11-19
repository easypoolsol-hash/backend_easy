"""
Integration tests for Face Enrollment API endpoints

Tests real HTTP requests through the full Django stack.
Uses fixtures from conftest.py for efficient test setup.
"""

import base64

import pytest
from rest_framework import status

from students.models import FaceEnrollment
from tests.factories import (
    FaceEnrollmentFactory,
    StudentFactory,
    StudentParentFactory,
)


def _create_valid_photo_base64():
    """Create valid base64 encoded image data"""
    fake_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100
    return base64.b64encode(fake_jpeg).decode()


@pytest.mark.django_db
class TestFaceEnrollmentSubmitEndpoint:
    """Tests for POST /api/v1/parents/me/{student_id}/face-enrollment/submit/"""

    def test_submit_success(self, approved_parent_client):
        """Approved parent can submit face enrollment for their child"""
        client, _user, parent = approved_parent_client

        # Create student linked to parent
        student = StudentFactory()
        StudentParentFactory(student=student, parent=parent)

        # Submit enrollment
        photos = [_create_valid_photo_base64() for _ in range(3)]
        response = client.post(
            f"/api/v1/parents/me/{student.student_id}/face-enrollment/submit/",
            data={
                "photos": photos,
                "device_info": {"app_version": "1.0.0", "platform": "android"},
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "pending_approval"
        assert response.data["photo_count"] == 3

        # Verify database record
        enrollment = FaceEnrollment.objects.get(student=student, parent=parent)
        assert enrollment.status == "pending_approval"
        assert len(enrollment.photos_data) == 3

    def test_submit_unapproved_parent_denied(self, unapproved_parent_client):
        """Unapproved parent cannot submit enrollment"""
        client, _user, parent = unapproved_parent_client

        student = StudentFactory()
        StudentParentFactory(student=student, parent=parent)

        photos = [_create_valid_photo_base64() for _ in range(3)]
        response = client.post(
            f"/api/v1/parents/me/{student.student_id}/face-enrollment/submit/",
            data={"photos": photos},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_submit_unauthenticated_denied(self, api_client):
        """Unauthenticated user cannot submit"""
        student = StudentFactory()

        response = api_client.post(
            f"/api/v1/parents/me/{student.student_id}/face-enrollment/submit/",
            data={"photos": [_create_valid_photo_base64() for _ in range(3)]},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_submit_wrong_student_denied(self, approved_parent_client):
        """Parent cannot submit for student not linked to them"""
        client, _user, _parent = approved_parent_client

        # Student NOT linked to this parent
        other_student = StudentFactory()

        photos = [_create_valid_photo_base64() for _ in range(3)]
        response = client.post(
            f"/api/v1/parents/me/{other_student.student_id}/face-enrollment/submit/",
            data={"photos": photos},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "not authorized" in response.data["error"].lower()

    def test_submit_invalid_photo_count(self, approved_parent_client):
        """Reject submission with wrong photo count"""
        client, _user, parent = approved_parent_client

        student = StudentFactory()
        StudentParentFactory(student=student, parent=parent)

        # Only 2 photos (minimum is 3)
        photos = [_create_valid_photo_base64() for _ in range(2)]
        response = client.post(
            f"/api/v1/parents/me/{student.student_id}/face-enrollment/submit/",
            data={"photos": photos},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "minimum" in str(response.data).lower()

    def test_submit_replaces_existing_pending(self, approved_parent_client):
        """New submission replaces existing pending enrollment"""
        client, _user, parent = approved_parent_client

        student = StudentFactory()
        StudentParentFactory(student=student, parent=parent)

        # Create existing pending enrollment
        old_enrollment = FaceEnrollmentFactory(
            student=student,
            parent=parent,
            status="pending_approval",
        )
        old_id = old_enrollment.enrollment_id

        # Submit new enrollment
        photos = [_create_valid_photo_base64() for _ in range(3)]
        response = client.post(
            f"/api/v1/parents/me/{student.student_id}/face-enrollment/submit/",
            data={"photos": photos},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED

        # Old enrollment should be deleted
        assert not FaceEnrollment.objects.filter(enrollment_id=old_id).exists()

        # New enrollment should exist
        new_enrollment = FaceEnrollment.objects.get(student=student, parent=parent)
        assert new_enrollment.enrollment_id != old_id


@pytest.mark.django_db
class TestFaceEnrollmentStatusEndpoint:
    """Tests for GET /api/v1/parents/me/{student_id}/face-enrollment/status/"""

    def test_get_status_success(self, approved_parent_client):
        """Get enrollment status for pending submission"""
        client, _user, parent = approved_parent_client

        student = StudentFactory()
        StudentParentFactory(student=student, parent=parent)

        # Create enrollment
        enrollment = FaceEnrollmentFactory(
            student=student,
            parent=parent,
            status="pending_approval",
        )

        response = client.get(
            f"/api/v1/parents/me/{student.student_id}/face-enrollment/status/",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "pending_approval"
        assert response.data["enrollment_id"] == str(enrollment.enrollment_id)

    def test_get_status_no_enrollment(self, approved_parent_client):
        """Return 404 when no enrollment exists"""
        client, _user, parent = approved_parent_client

        student = StudentFactory()
        StudentParentFactory(student=student, parent=parent)

        response = client.get(
            f"/api/v1/parents/me/{student.student_id}/face-enrollment/status/",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_status_unapproved_parent_denied(self, unapproved_parent_client):
        """Unapproved parent cannot check status"""
        client, _user, parent = unapproved_parent_client

        student = StudentFactory()
        StudentParentFactory(student=student, parent=parent)

        response = client.get(
            f"/api/v1/parents/me/{student.student_id}/face-enrollment/status/",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_status_wrong_student_denied(self, approved_parent_client):
        """Parent cannot check status for unlinked student"""
        client, _user, _parent = approved_parent_client

        # Student NOT linked to this parent
        other_student = StudentFactory()

        response = client.get(
            f"/api/v1/parents/me/{other_student.student_id}/face-enrollment/status/",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize(
        "status_value",
        ["pending_approval", "approved", "rejected"],
    )
    def test_get_various_statuses(self, approved_parent_client, status_value):
        """Correctly return different status values"""
        client, _user, parent = approved_parent_client

        student = StudentFactory()
        StudentParentFactory(student=student, parent=parent)

        FaceEnrollmentFactory(
            student=student,
            parent=parent,
            status=status_value,
        )

        response = client.get(
            f"/api/v1/parents/me/{student.student_id}/face-enrollment/status/",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == status_value
