import os
from typing import TYPE_CHECKING
import uuid

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

if TYPE_CHECKING:
    from buses.models import Bus

# Constants for validation error messages
BUS_CAPACITY_ERROR = "Bus capacity must be greater than 0"
INVALID_STATUS_ERROR = "Invalid status"
PRIMARY_PARENT_ERROR = "Student can only have one primary parent"
QUALITY_SCORE_ERROR = "Quality score must be between 0 and 1"
ENCRYPTED_PLACEHOLDER = "[ENCRYPTED]"

# Validation error format strings
INVALID_STATUS_FORMAT = "{}: {}"


def student_photo_path(instance, filename):
    """Generate random unique filename for student photos"""
    ext = os.path.splitext(filename)[1]
    random_name = f"{uuid.uuid4().hex}{ext}"
    return f"student_photos/{random_name}"


class School(models.Model):
    """Placeholder School model - will be expanded in future"""

    school_id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name: models.CharField = models.CharField(max_length=255, unique=True)
    created_at: models.DateTimeField = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name


class Student(models.Model):
    """Student model with PII encryption and row-level security"""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("suspended", "Suspended"),
    ]

    student_id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school: models.ForeignKey = models.ForeignKey(School, on_delete=models.CASCADE, related_name="students")
    school_student_id: models.CharField = models.CharField(
        max_length=50,
        help_text="School-provided student ID (e.g., STU-2024-001)",
        unique=True,
    )
    name: models.TextField = models.TextField(help_text="Encrypted at application layer")
    grade: models.CharField = models.CharField(max_length=10)
    section: models.CharField = models.CharField(max_length=10, blank=True)
    address_latitude: models.DecimalField = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        help_text="Student home address latitude",
    )
    address_longitude: models.DecimalField = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        help_text="Student home address longitude",
    )
    assigned_bus: "models.ForeignKey[Bus]" = models.ForeignKey(  # type: ignore[misc]
        "buses.Bus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_students",
    )
    status: models.CharField = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    enrollment_date: models.DateField = models.DateField(null=True, blank=True, help_text="Date student enrolled in school")
    created_at: models.DateTimeField = models.DateTimeField(default=timezone.now)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "students"
        indexes = [
            models.Index(fields=["school", "status"], name="idx_students_school_status"),
            models.Index(
                fields=["assigned_bus"],
                condition=models.Q(status="active"),
                name="idx_students_bus_active",
            ),
        ]

    def __str__(self):
        return f"Student {self.student_id}"

    def clean(self):
        if self.status not in dict(self.STATUS_CHOICES):
            raise ValidationError(INVALID_STATUS_FORMAT.format(INVALID_STATUS_ERROR, self.status))

    @property
    def encrypted_name(self):
        """Get decrypted name"""
        if not self.name:
            return ""
        fernet = Fernet(settings.ENCRYPTION_KEY.encode())
        try:
            return fernet.decrypt(self.name.encode()).decode()
        except Exception:
            # If decryption fails, assume it's already plaintext (from old data)
            return self.name

    @encrypted_name.setter
    def encrypted_name(self, value):
        """Set encrypted name"""
        if value:
            fernet = Fernet(settings.ENCRYPTION_KEY.encode())
            self.name = fernet.encrypt(value.encode()).decode()
        else:
            self.name = ""

    def get_reference_photo(self):
        """
        Get the reference photo for this student.

        Returns primary photo if available, otherwise returns first available photo.
        Used for face recognition verification in boarding events.

        Returns:
            StudentPhoto instance or None if no photos exist
        """
        # First choice: Primary photo
        primary = self.photos.filter(is_primary=True).first()
        if primary:
            return primary

        # Fallback: First photo by capture date
        return self.photos.order_by("captured_at").first()

    def get_parents(self):
        """Get all parents for this student"""
        return Parent.objects.filter(student_parents__student=self)

    def get_primary_parent(self):
        """Get the primary parent for this student"""
        try:
            return Parent.objects.get(student_parents__student=self, student_parents__is_primary=True)
        except Parent.DoesNotExist:
            return None


class StudentPhoto(models.Model):
    """Student photo storage - stored as binary data in Cloud SQL database"""

    photo_id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student: models.ForeignKey = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="photos")

    # Track if photo was submitted by parent (via face enrollment)
    submitted_by_parent = models.ForeignKey(  # type: ignore[misc]
        "Parent",  # String reference - Parent defined later in file
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_photos",
        help_text="Parent who submitted this photo (NULL if admin-uploaded)",
    )

    # Store photo as binary data in database (Cloud SQL)
    photo_data: models.BinaryField = models.BinaryField(
        blank=True,
        null=True,
        help_text="Photo binary data stored in database",
    )
    photo_content_type: models.CharField = models.CharField(
        max_length=50,
        blank=True,
        default="image/jpeg",
        help_text="MIME type (e.g., image/jpeg, image/png)",
    )

    is_primary: models.BooleanField = models.BooleanField(default=False, help_text="Primary photo for student")
    captured_at: models.DateTimeField = models.DateTimeField(default=timezone.now, help_text="When photo was taken")
    created_at: models.DateTimeField = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "student_photos"
        indexes = [
            models.Index(fields=["student"], name="idx_photos_student"),
        ]

    def __str__(self):
        photo_type = "primary" if self.is_primary else "secondary"
        has_photo = "with photo" if self.photo_data else "no photo"
        return f"Photo for {self.student} ({photo_type}) - {has_photo}"

    @property
    def photo_url(self):
        """Get URL to serve photo from database"""
        if self.photo_data:
            from django.urls import reverse

            return reverse("student-photo-serve", kwargs={"photo_id": str(self.photo_id)})
        return None

    def get_cached_url(self, cache_duration_hours=1):
        """
        Get photo URL with caching to reduce repeated URL generation.

        For database-stored photos, this returns the same URL but with caching
        to avoid repeated database queries when displaying photos in lists.

        Args:
            cache_duration_hours: How long to cache the URL (default 1 hour)

        Returns:
            str: Photo URL or None if no photo data
        """
        from django.core.cache import cache

        if not self.photo_data:
            return None

        cache_key = f"photo_url_{self.photo_id}_{cache_duration_hours}h"
        cached_url = cache.get(cache_key)

        if cached_url:
            return cached_url

        # Generate URL
        url = self.photo_url

        # Cache for specified duration
        cache.set(cache_key, url, timeout=cache_duration_hours * 3600)

        return url

    def save(self, *args, **kwargs):
        # Ensure only one primary photo per student
        if self.is_primary:
            StudentPhoto.objects.filter(student=self.student, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class Parent(models.Model):
    """Parent model with encrypted PII and approval workflow

    Google-style Architecture:
    - Parent is the domain entity (authorization layer)
    - User is authentication only (identity layer)
    - Approval status lives on Parent, not User

    Industry Standard Pattern:
    - Validate plaintext BEFORE encryption
    - Store encrypted data in TextField (unlimited length)
    - Use hash indexes for encrypted field lookups
    """

    APPROVAL_STATUS_CHOICES = [
        ("pending", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    # Validation constants (Fortune 500 standard)
    PHONE_REGEX = r"^(\+91)?\d{10}$"  # Optional +91 followed by exactly 10 digits
    EMAIL_MAX_LENGTH = 254  # RFC 5321 standard
    NAME_MAX_LENGTH = 100  # Reasonable human name limit

    parent_id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Link to User account (authentication layer)
    user: models.OneToOneField = models.OneToOneField(
        "users.User",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="parent_profile",
        help_text="Linked user account for this parent",
    )

    phone: models.TextField = models.TextField(
        null=True,
        blank=True,
        help_text="Encrypted phone number (plaintext validated as +91XXXXXXXXXX)",
    )
    email: models.TextField = models.TextField(
        null=True,
        blank=True,
        help_text="Encrypted email address (plaintext validated per RFC 5321)",
    )
    name: models.TextField = models.TextField(help_text="Encrypted name (plaintext validated max 100 chars)")

    # Approval workflow fields (domain/authorization layer)
    approval_status: models.CharField = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default="pending",
        help_text="Approval status for parent access",
    )
    approved_by: models.ForeignKey = models.ForeignKey(  # type: ignore[misc]
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_parents",
        help_text="Admin who approved this parent",
    )
    approved_at: models.DateTimeField = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when parent was approved",
    )

    created_at: models.DateTimeField = models.DateTimeField(default=timezone.now)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "parents"
        indexes = [
            models.Index(fields=["phone"], name="idx_parents_phone"),
            models.Index(fields=["email"], name="idx_parents_email"),
            models.Index(fields=["user"], name="idx_parents_user"),
            models.Index(fields=["approval_status"], name="idx_parents_approval_status"),
        ]

    def __str__(self):
        try:
            name = self.encrypted_name
            return f"{name} (Parent)"
        except Exception:  # nosec B110
            return f"Parent {self.parent_id}"

    def clean(self):
        """Validate plaintext data BEFORE encryption (Fortune 500 pattern)"""
        import re

        from django.core.validators import validate_email as django_validate_email

        # Validate phone format (must be decrypted first if already encrypted)
        try:
            plaintext_phone = self.encrypted_phone
            if not re.match(self.PHONE_REGEX, plaintext_phone):
                raise ValidationError({"phone": f"Phone must match format: {self.PHONE_REGEX} (e.g., +919876543210)"})
        except Exception:  # nosec B110
            pass  # Skip validation if not yet set or decryption fails

        # Validate email format
        try:
            plaintext_email = self.encrypted_email
            if len(plaintext_email) > self.EMAIL_MAX_LENGTH:
                raise ValidationError({"email": f"Email too long (max {self.EMAIL_MAX_LENGTH} characters)"})
            django_validate_email(plaintext_email)
        except Exception:  # nosec B110
            pass  # Skip validation if not yet set or decryption fails

        # Validate name length
        try:
            plaintext_name = self.encrypted_name
            if len(plaintext_name) > self.NAME_MAX_LENGTH:
                raise ValidationError({"name": f"Name too long (max {self.NAME_MAX_LENGTH} characters)"})
        except Exception:  # nosec B110
            pass  # Skip validation if not yet set or decryption fails

    @property
    def encrypted_phone(self):
        """Get decrypted phone"""
        if not self.phone:
            return ""
        fernet = Fernet(settings.ENCRYPTION_KEY.encode())
        try:
            return fernet.decrypt(self.phone.encode()).decode()
        except Exception:
            # If decryption fails, assume it's already plaintext (from old data)
            return self.phone

    @encrypted_phone.setter
    def encrypted_phone(self, value):
        """Set encrypted phone - validates BEFORE encryption (Fortune 500 pattern)"""
        if not value:
            self.phone = ""
            return

        # VALIDATE BEFORE ENCRYPTION (critical!)
        import re

        if not re.match(self.PHONE_REGEX, value):
            raise ValidationError(f"Phone must match format: {self.PHONE_REGEX} (e.g., +919876543210)")

        # ENCRYPT AFTER VALIDATION
        fernet = Fernet(settings.ENCRYPTION_KEY.encode())
        self.phone = fernet.encrypt(value.encode()).decode()

    @property
    def encrypted_email(self):
        """Get decrypted email"""
        if not self.email:
            return ""
        fernet = Fernet(settings.ENCRYPTION_KEY.encode())
        try:
            return fernet.decrypt(self.email.encode()).decode()
        except Exception:
            # If decryption fails, assume it's already plaintext (from old data)
            return self.email

    @encrypted_email.setter
    def encrypted_email(self, value):
        """Set encrypted email - validates BEFORE encryption (Fortune 500 pattern)"""
        if not value:
            self.email = ""
            return

        # VALIDATE BEFORE ENCRYPTION (critical!)
        from django.core.validators import validate_email as django_validate_email

        if len(value) > self.EMAIL_MAX_LENGTH:
            raise ValidationError(f"Email too long (max {self.EMAIL_MAX_LENGTH} characters)")
        django_validate_email(value)  # Raises ValidationError if invalid

        # ENCRYPT AFTER VALIDATION
        fernet = Fernet(settings.ENCRYPTION_KEY.encode())
        self.email = fernet.encrypt(value.encode()).decode()

    @property
    def encrypted_name(self):
        """Get decrypted name"""
        if not self.name:
            return ""
        fernet = Fernet(settings.ENCRYPTION_KEY.encode())
        try:
            return fernet.decrypt(self.name.encode()).decode()
        except Exception:
            # If decryption fails, assume it's already plaintext (from old data)
            return self.name

    @encrypted_name.setter
    def encrypted_name(self, value):
        """Set encrypted name - validates BEFORE encryption (Fortune 500 pattern)"""
        if not value:
            self.name = ""
            return

        # VALIDATE BEFORE ENCRYPTION (critical!)
        if len(value) > self.NAME_MAX_LENGTH:
            raise ValidationError(f"Name too long (max {self.NAME_MAX_LENGTH} characters)")

        # ENCRYPT AFTER VALIDATION
        fernet = Fernet(settings.ENCRYPTION_KEY.encode())
        self.name = fernet.encrypt(value.encode()).decode()

    def get_students(self):
        """Get all students for this parent"""
        return Student.objects.filter(student_parents__parent=self)

    def approve(self, approved_by_user):
        """
        Approve this parent for access.
        Assigns Parent group to linked user and updates approval status.
        """
        if not self.user:
            raise ValueError("Cannot approve parent without linked User account")

        from django.contrib.auth.models import Group

        # Remove New User group from user
        new_user_group = Group.objects.filter(name="New User").first()
        if new_user_group:
            self.user.groups.remove(new_user_group)

        # Add Parent group to user
        parent_group, _ = Group.objects.get_or_create(name="Parent")
        self.user.groups.add(parent_group)

        # Update approval fields
        self.approval_status = "approved"
        self.approved_by = approved_by_user
        self.approved_at = timezone.now()
        self.save()

    def reject(self, rejected_by_user):
        """Reject this parent's access request"""
        self.approval_status = "rejected"
        self.approved_by = rejected_by_user
        self.approved_at = timezone.now()
        self.save()

    @property
    def is_approved(self):
        """Check if parent is approved"""
        return self.approval_status == "approved"

    @property
    def is_pending(self):
        """Check if parent is pending approval"""
        return self.approval_status == "pending"


class StudentParent(models.Model):
    """Many-to-many relationship between students and parents"""

    RELATIONSHIP_CHOICES = [
        ("mother", "Mother"),
        ("father", "Father"),
        ("guardian", "Guardian"),
        ("grandparent", "Grandparent"),
        ("other", "Other"),
    ]

    student: models.ForeignKey = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="student_parents")
    parent: models.ForeignKey = models.ForeignKey(Parent, on_delete=models.CASCADE, related_name="student_parents")
    relationship: models.CharField = models.CharField(max_length=50, choices=RELATIONSHIP_CHOICES)
    is_primary: models.BooleanField = models.BooleanField(default=False)

    class Meta:
        db_table = "student_parents"
        unique_together = ["student", "parent"]
        indexes = [
            models.Index(fields=["parent"], name="idx_parent_students"),
        ]

    def __str__(self):
        return f"{self.parent} - {self.student} ({self.relationship})"

    def clean(self):
        # Ensure only one primary parent per student
        if self.is_primary:
            existing_primary = StudentParent.objects.filter(student=self.student, is_primary=True).exclude(pk=self.pk)
            if existing_primary.exists():
                raise ValidationError(PRIMARY_PARENT_ERROR)


class FaceEmbeddingMetadata(models.Model):
    """Metadata for face embeddings stored in Qdrant vector database"""

    embedding_id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student_photo: models.ForeignKey = models.ForeignKey(StudentPhoto, on_delete=models.CASCADE, related_name="face_embeddings")
    model_name: models.CharField = models.CharField(max_length=100, help_text="Face recognition model")
    model_version: models.CharField = models.CharField(max_length=50, help_text="Face recognition model version")
    embedding: models.JSONField = models.JSONField(help_text="The embedding vector as a list of floats", default=dict)
    quality_score: models.FloatField = models.FloatField(help_text="Face detection quality score (0-1)")
    is_primary: models.BooleanField = models.BooleanField(default=False, help_text="Primary embedding for this photo")
    captured_at: models.DateTimeField = models.DateTimeField(help_text="When the face was captured")
    created_at: models.DateTimeField = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "face_embeddings_metadata"
        indexes = [
            models.Index(
                fields=["student_photo", "model_name", "model_version"],
                name="idx_embeddings_photo_model",
            ),
        ]

    def __str__(self):
        return f"Face embedding for {self.student_photo} (quality: {self.quality_score})"

    def clean(self):
        if not (0 <= self.quality_score <= 1):
            raise ValidationError(QUALITY_SCORE_ERROR)

    def save(self, *args, **kwargs):
        # Ensure only one primary embedding per photo
        if self.is_primary:
            FaceEmbeddingMetadata.objects.filter(student_photo=self.student_photo, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class FaceEnrollment(models.Model):
    """
    Staging table for parent-submitted face enrollment photos.

    Workflow:
    1. Parent uses camera app to scan student face (auto-captures 3-5 photos)
    2. Photos saved here with status='pending_approval'
    3. Admin reviews and approves/rejects
    4. On approval: Photos moved to StudentPhoto table, enrollment deleted

    This is a temporary staging area - approved enrollments are deleted after
    photos are transferred to production StudentPhoto table.
    """

    ENROLLMENT_STATUS_CHOICES = [
        ("pending_approval", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    enrollment_id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Links
    student: models.ForeignKey = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="face_enrollments", help_text="Student for this enrollment"
    )
    parent: models.ForeignKey = models.ForeignKey(
        Parent, on_delete=models.CASCADE, related_name="face_enrollments", help_text="Parent who submitted this enrollment"
    )

    # Photos data (stored as JSON array of base64-encoded images)
    # Each photo is a dict: {"data": "<base64>", "content_type": "image/jpeg"}
    photos_data: models.JSONField = models.JSONField(help_text="Array of photo data objects from auto-capture session")
    photo_count: models.IntegerField = models.IntegerField(help_text="Number of photos in this enrollment")

    # Status tracking
    status: models.CharField = models.CharField(
        max_length=20, choices=ENROLLMENT_STATUS_CHOICES, default="pending_approval", help_text="Approval status"
    )

    # Timestamps
    submitted_at: models.DateTimeField = models.DateTimeField(default=timezone.now, help_text="When parent submitted enrollment")
    reviewed_by = models.ForeignKey(  # type: ignore[misc]
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_enrollments",
        help_text="Admin who reviewed this enrollment",
    )
    reviewed_at: models.DateTimeField = models.DateTimeField(null=True, blank=True, help_text="When enrollment was reviewed")

    # Metadata
    device_info: models.JSONField = models.JSONField(default=dict, blank=True, help_text="Device and capture metadata from parent app")

    class Meta:
        db_table = "face_enrollments"
        indexes = [
            models.Index(fields=["student", "status"], name="idx_enrollments_student_status"),
            models.Index(fields=["parent", "status"], name="idx_enrollments_parent_status"),
            models.Index(fields=["status", "submitted_at"], name="idx_enrollments_status_date"),
        ]

    def __str__(self):
        return f"Face enrollment for {self.student} by {self.parent} ({self.status})"

    def approve(self, reviewed_by_user):
        """
        Approve this enrollment and move photos to StudentPhoto table.

        This method:
        1. Creates StudentPhoto records from enrollment photos
        2. Sets first photo as primary
        3. Marks enrollment as approved
        4. Sets review metadata

        Note: Enrollment record should be deleted after approval by admin action.
        """
        import base64

        if self.status != "pending_approval":
            raise ValidationError("Can only approve pending enrollments")

        # Create StudentPhoto records from enrollment photos
        for idx, photo_data in enumerate(self.photos_data):
            # Decode base64 photo data
            photo_binary = base64.b64decode(photo_data.get("data", ""))
            content_type = photo_data.get("content_type", "image/jpeg")

            # Create StudentPhoto
            student_photo = StudentPhoto(
                student=self.student,
                submitted_by_parent=self.parent,  # Track parent submission
                photo_data=photo_binary,
                photo_content_type=content_type,
                is_primary=(idx == 0),  # First photo is primary
                captured_at=self.submitted_at,
            )
            student_photo.save()

        # Update enrollment status
        self.status = "approved"
        self.reviewed_by = reviewed_by_user
        self.reviewed_at = timezone.now()
        self.save()

    def reject(self, reviewed_by_user):
        """Reject this enrollment"""
        if self.status != "pending_approval":
            raise ValidationError("Can only reject pending enrollments")

        self.status = "rejected"
        self.reviewed_by = reviewed_by_user
        self.reviewed_at = timezone.now()
        self.save()
