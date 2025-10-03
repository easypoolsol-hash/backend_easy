import uuid

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

# Constants for validation error messages
BUS_CAPACITY_ERROR = "Bus capacity must be greater than 0"
INVALID_STATUS_ERROR = "Invalid status"
PRIMARY_PARENT_ERROR = "Student can only have one primary parent"
QUALITY_SCORE_ERROR = "Quality score must be between 0 and 1"
ENCRYPTED_PLACEHOLDER = "[ENCRYPTED]"

# Validation error format strings
INVALID_STATUS_FORMAT = "{}: {}"


class School(models.Model):
    """Placeholder School model - will be expanded in future"""
    school_id: models.UUIDField = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    name: models.CharField = models.CharField(max_length=255, unique=True)
    created_at: models.DateTimeField = models.DateTimeField(
        default=timezone.now
    )

    def __str__(self):
        return self.name


class Bus(models.Model):
    """Placeholder Bus model - will be expanded in buses app"""
    BUS_STATUS_CHOICES = [
        ('active', 'Active'),
        ('maintenance', 'Maintenance'),
        ('retired', 'Retired'),
    ]

    bus_id: models.UUIDField = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    license_plate: models.CharField = models.CharField(
        max_length=20, unique=True
    )
    capacity: models.PositiveIntegerField = models.PositiveIntegerField()
    status: models.CharField = models.CharField(
        max_length=20, choices=BUS_STATUS_CHOICES, default='active'
    )
    created_at: models.DateTimeField = models.DateTimeField(
        default=timezone.now
    )
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.license_plate}"

    def clean(self):
        if self.capacity <= 0:
            raise ValidationError(BUS_CAPACITY_ERROR)


class Student(models.Model):
    """Student model with PII encryption and row-level security"""

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
    ]

    student_id: models.UUIDField = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    school: models.ForeignKey = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name='students'
    )
    name: models.TextField = models.TextField(
        help_text="Encrypted at application layer"
    )
    grade: models.CharField = models.CharField(max_length=10)
    section: models.CharField = models.CharField(max_length=10, blank=True)
    assigned_bus: models.ForeignKey = models.ForeignKey(  # type: ignore[misc]
        Bus,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_students'
    )
    status: models.CharField = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='active'
    )
    enrollment_date: models.DateField = models.DateField()
    created_at: models.DateTimeField = models.DateTimeField(
        default=timezone.now
    )
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'students'
        indexes = [
            models.Index(
                fields=['school', 'status'],
                name='idx_students_school_status'
            ),
            models.Index(
                fields=['assigned_bus'],
                condition=models.Q(status='active'),
                name='idx_students_bus_active'
            ),
        ]

    def __str__(self):
        return f"Student {self.student_id}"

    def clean(self):
        if self.status not in dict(self.STATUS_CHOICES):
            raise ValidationError(
                INVALID_STATUS_FORMAT.format(INVALID_STATUS_ERROR, self.status)
            )

    @property
    def encrypted_name(self):
        """Get decrypted name"""
        if not self.name:
            return ""
        fernet = Fernet(settings.ENCRYPTION_KEY.encode())
        try:
            return fernet.decrypt(self.name.encode()).decode()
        except (ValueError, TypeError):
            return ENCRYPTED_PLACEHOLDER

    @encrypted_name.setter
    def encrypted_name(self, value):
        """Set encrypted name"""
        if value:
            fernet = Fernet(settings.ENCRYPTION_KEY.encode())
            self.name = fernet.encrypt(value.encode()).decode()
        else:
            self.name = ""

    def get_parents(self):
        """Get all parents for this student"""
        return Parent.objects.filter(student_parents__student=self)

    def get_primary_parent(self):
        """Get the primary parent for this student"""
        try:
            return Parent.objects.get(
                student_parents__student=self,
                student_parents__is_primary=True
            )
        except Parent.DoesNotExist:
            return None


class StudentPhoto(models.Model):
    """Student photo storage with support for multiple photos per student"""

    photo_id: models.UUIDField = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    student: models.ForeignKey = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='photos'
    )
    photo_url: models.TextField = models.TextField(
        help_text="S3 path to student photo"
    )
    is_primary: models.BooleanField = models.BooleanField(
        default=False, help_text="Primary photo for student"
    )
    captured_at: models.DateTimeField = models.DateTimeField(
        default=timezone.now, help_text="When photo was taken"
    )
    created_at: models.DateTimeField = models.DateTimeField(
        default=timezone.now
    )

    class Meta:
        db_table = 'student_photos'
        indexes = [
            models.Index(fields=['student'], name='idx_photos_student'),
        ]

    def __str__(self):
        photo_type = 'primary' if self.is_primary else 'secondary'
        return f"Photo for {self.student} ({photo_type})"

    def save(self, *args, **kwargs):
        # Ensure only one primary photo per student
        if self.is_primary:
            StudentPhoto.objects.filter(
                student=self.student,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class Parent(models.Model):
    """Parent model with encrypted PII"""

    parent_id: models.UUIDField = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    phone: models.CharField = models.CharField(
        max_length=20, unique=True, help_text="Encrypted"
    )
    email: models.EmailField = models.EmailField(
        unique=True, help_text="Encrypted"
    )
    name: models.TextField = models.TextField(help_text="Encrypted")
    created_at: models.DateTimeField = models.DateTimeField(
        default=timezone.now
    )

    class Meta:
        db_table = 'parents'
        indexes = [
            models.Index(fields=['phone'], name='idx_parents_phone'),
            models.Index(fields=['email'], name='idx_parents_email'),
        ]

    def __str__(self):
        return f"Parent {self.parent_id}"

    @property
    def encrypted_phone(self):
        """Get decrypted phone"""
        if not self.phone:
            return ""
        fernet = Fernet(settings.ENCRYPTION_KEY.encode())
        try:
            return fernet.decrypt(self.phone.encode()).decode()
        except (ValueError, TypeError):
            return ENCRYPTED_PLACEHOLDER

    @encrypted_phone.setter
    def encrypted_phone(self, value):
        """Set encrypted phone"""
        if value:
            fernet = Fernet(settings.ENCRYPTION_KEY.encode())
            self.phone = fernet.encrypt(value.encode()).decode()
        else:
            self.phone = ""

    @property
    def encrypted_email(self):
        """Get decrypted email"""
        if not self.email:
            return ""
        fernet = Fernet(settings.ENCRYPTION_KEY.encode())
        try:
            return fernet.decrypt(self.email.encode()).decode()
        except (ValueError, TypeError):
            return ENCRYPTED_PLACEHOLDER

    @encrypted_email.setter
    def encrypted_email(self, value):
        """Set encrypted email"""
        if value:
            fernet = Fernet(settings.ENCRYPTION_KEY.encode())
            self.email = fernet.encrypt(value.encode()).decode()
        else:
            self.email = ""

    @property
    def encrypted_name(self):
        """Get decrypted name"""
        if not self.name:
            return ""
        fernet = Fernet(settings.ENCRYPTION_KEY.encode())
        try:
            return fernet.decrypt(self.name.encode()).decode()
        except (ValueError, TypeError):
            return ENCRYPTED_PLACEHOLDER

    @encrypted_name.setter
    def encrypted_name(self, value):
        """Set encrypted name"""
        if value:
            fernet = Fernet(settings.ENCRYPTION_KEY.encode())
            self.name = fernet.encrypt(value.encode()).decode()
        else:
            self.name = ""

    def get_students(self):
        """Get all students for this parent"""
        return Student.objects.filter(student_parents__parent=self)


class StudentParent(models.Model):
    """Many-to-many relationship between students and parents"""

    RELATIONSHIP_CHOICES = [
        ('mother', 'Mother'),
        ('father', 'Father'),
        ('guardian', 'Guardian'),
        ('grandparent', 'Grandparent'),
        ('other', 'Other'),
    ]

    student: models.ForeignKey = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='student_parents'
    )
    parent: models.ForeignKey = models.ForeignKey(
        Parent, on_delete=models.CASCADE, related_name='student_parents'
    )
    relationship: models.CharField = models.CharField(
        max_length=50, choices=RELATIONSHIP_CHOICES
    )
    is_primary: models.BooleanField = models.BooleanField(default=False)

    class Meta:
        db_table = 'student_parents'
        unique_together = ['student', 'parent']
        indexes = [
            models.Index(fields=['parent'], name='idx_parent_students'),
        ]

    def __str__(self):
        return f"{self.parent} - {self.student} ({self.relationship})"

    def clean(self):
        # Ensure only one primary parent per student
        if self.is_primary:
            existing_primary = StudentParent.objects.filter(
                student=self.student,
                is_primary=True
            ).exclude(pk=self.pk)
            if existing_primary.exists():
                raise ValidationError(PRIMARY_PARENT_ERROR)


class FaceEmbeddingMetadata(models.Model):
    """Metadata for face embeddings stored in Qdrant vector database"""

    embedding_id: models.UUIDField = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    student_photo: models.ForeignKey = models.ForeignKey(
        StudentPhoto,
        on_delete=models.CASCADE,
        related_name='face_embeddings'
    )
    model_name: models.CharField = models.CharField(
        max_length=100, help_text="Face recognition model"
    )
    model_version: models.CharField = models.CharField(
        max_length=50, help_text="Face recognition model version"
    )
    qdrant_point_id: models.CharField = models.CharField(
        max_length=100, unique=True, help_text="Reference to Qdrant point"
    )
    quality_score: models.FloatField = models.FloatField(
        help_text="Face detection quality score (0-1)"
    )
    is_primary: models.BooleanField = models.BooleanField(
        default=False, help_text="Primary embedding for this photo"
    )
    captured_at: models.DateTimeField = models.DateTimeField(
        help_text="When the face was captured"
    )
    created_at: models.DateTimeField = models.DateTimeField(
        default=timezone.now
    )

    class Meta:
        db_table = 'face_embeddings_metadata'
        indexes = [
            models.Index(
                fields=['student_photo', 'model_name', 'model_version'],
                name='idx_embeddings_photo_model'
            ),
        ]

    def __str__(self):
        return (
            f"Face embedding for {self.student_photo} "
            f"(quality: {self.quality_score})"
        )

    def clean(self):
        if not (0 <= self.quality_score <= 1):
            raise ValidationError(QUALITY_SCORE_ERROR)

    def save(self, *args, **kwargs):
        # Ensure only one primary embedding per photo
        if self.is_primary:
            FaceEmbeddingMetadata.objects.filter(
                student_photo=self.student_photo,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)
