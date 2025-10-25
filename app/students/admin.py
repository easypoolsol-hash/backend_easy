from django import forms
from django.contrib import admin
from django.contrib.admin import display
from django.utils.html import format_html

from .models import (
    FaceEmbeddingMetadata,
    Parent,
    School,
    Student,
    StudentParent,
    StudentPhoto,
)


class StudentAdminForm(forms.ModelForm):
    """Custom form to handle encrypted fields in admin"""

    # Use a regular CharField for name input (plaintext)
    plaintext_name = forms.CharField(
        label="Name",
        max_length=255,
        help_text="Enter student's name (will be encrypted automatically)",
    )

    class Meta:
        model = Student
        fields = [
            "school",
            "school_student_id",
            "plaintext_name",
            "grade",
            "section",
            "assigned_bus",
            "status",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-fill with decrypted name if editing existing student
        if self.instance and self.instance.pk:
            try:
                decrypted = self.instance.encrypted_name
                self.fields["plaintext_name"].initial = decrypted
            except Exception:
                self.fields["plaintext_name"].initial = ""

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Encrypt the plaintext name before saving
        instance.encrypted_name = self.cleaned_data["plaintext_name"]
        if commit:
            instance.save()
        return instance


class ParentAdminForm(forms.ModelForm):
    """Custom form to handle encrypted parent fields in admin"""

    plaintext_name = forms.CharField(
        label="Name",
        max_length=255,
        help_text="Enter parent's name (will be encrypted automatically)",
    )
    plaintext_phone = forms.CharField(
        label="Phone",
        max_length=20,
        help_text="Enter phone number (will be encrypted automatically)",
    )
    plaintext_email = forms.EmailField(
        label="Email",
        help_text="Enter email address (will be encrypted automatically)",
    )

    class Meta:
        model = Parent
        fields = ["plaintext_name", "plaintext_phone", "plaintext_email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-fill with decrypted values if editing
        if self.instance and self.instance.pk:
            try:
                name = self.instance.encrypted_name
                self.fields["plaintext_name"].initial = name
                phone = self.instance.encrypted_phone
                self.fields["plaintext_phone"].initial = phone
                email = self.instance.encrypted_email
                self.fields["plaintext_email"].initial = email
            except Exception:
                pass

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Encrypt all fields before saving
        instance.encrypted_name = self.cleaned_data["plaintext_name"]
        instance.encrypted_phone = self.cleaned_data["plaintext_phone"]
        instance.encrypted_email = self.cleaned_data["plaintext_email"]
        if commit:
            instance.save()
        return instance


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ["school_id", "name", "created_at"]
    search_fields = ["name"]
    readonly_fields = ["school_id", "created_at"]


NO_PHOTO = "No photo"


class StudentPhotoInline(admin.TabularInline):
    model = StudentPhoto
    extra = 1  # Allow adding new photos inline
    fields = ["photo", "is_primary", "captured_at", "photo_preview"]
    readonly_fields = ["captured_at", "photo_preview"]

    @display(description="Preview")
    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" width="100" height="100" />', obj.photo.url)
        return NO_PHOTO


class StudentParentInline(admin.TabularInline):
    """Inline to link/unlink parents to student (parent details edited in Parent admin only)"""

    model = StudentParent
    extra = 1  # Allow adding at least one parent
    min_num = 1  # Require at least one parent
    validate_min = True
    fields = ["parent", "get_parent_phone", "get_parent_email", "relationship", "is_primary"]
    readonly_fields = ["get_parent_phone", "get_parent_email"]  # Can't edit parent info here
    autocomplete_fields = ["parent"]  # Searchable parent dropdown

    @display(description="Phone")
    def get_parent_phone(self, obj):
        if obj and obj.parent:
            try:
                return obj.parent.encrypted_phone
            except (AttributeError, ValueError):
                return obj.parent.phone
        return "-"

    @display(description="Email")
    def get_parent_email(self, obj):
        if obj and obj.parent:
            try:
                return obj.parent.encrypted_email
            except (AttributeError, ValueError):
                return obj.parent.email
        return "-"


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    form = StudentAdminForm  # Use custom form with encryption
    list_display = [
        "school_student_id",
        "get_name",
        "grade",
        "section",
        "get_primary_parent",
        "assigned_bus",
        "status",
    ]
    list_filter = ["status", "grade", "school"]
    search_fields = ["school_student_id", "student_id"]
    readonly_fields = ["student_id", "created_at", "updated_at"]
    inlines = [StudentParentInline, StudentPhotoInline]  # Parents first, then photos

    @display(description="Student Name")
    def get_name(self, obj):
        try:
            return obj.encrypted_name
        except Exception:
            # If decryption fails, return the raw name (likely not encrypted)
            return obj.name

    @display(description="Primary Parent")
    def get_primary_parent(self, obj):
        try:
            primary = obj.student_parents.filter(is_primary=True).first()
            if primary and primary.parent:
                parent_name = primary.parent.encrypted_name
                return format_html('<a href="/admin/students/parent/{}/change/">{}</a>', primary.parent.parent_id, parent_name)
            return format_html('<span style="color: orange;">No primary parent</span>')
        except Exception:
            return "-"


class FaceEmbeddingInline(admin.TabularInline):
    model = FaceEmbeddingMetadata
    extra = 0
    fields = ["model_name", "quality_score", "is_primary", "embedding"]
    readonly_fields = ["embedding", "created_at"]


@admin.register(StudentPhoto)
class StudentPhotoAdmin(admin.ModelAdmin):
    list_display = [
        "photo_id",
        "student",
        "photo_thumbnail",
        "is_primary",
        "captured_at",
        "embedding_count",
    ]
    list_filter = ["is_primary", "captured_at"]
    search_fields = ["student__name"]
    readonly_fields = ["photo_id", "created_at", "photo_preview"]
    inlines = [FaceEmbeddingInline]
    fields = [
        "student",
        "photo",
        "photo_preview",
        "is_primary",
        "captured_at",
        "photo_id",
        "created_at",
    ]

    @display(description="Thumbnail")
    def photo_thumbnail(self, obj):
        if obj.photo:
            return format_html('<img src="{}" width="50" height="50" />', obj.photo.url)
        return NO_PHOTO

    @display(description="Photo Preview")
    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" width="300" />', obj.photo.url)
        return NO_PHOTO

    @display(description="Embeddings")
    def embedding_count(self, obj):
        count = obj.face_embeddings.count()
        if count > 0:
            return format_html('<span style="color: green;">✓ {}</span>', count)
        return format_html('<span style="color: red;">✗ 0</span>')


class ParentStudentsInline(admin.TabularInline):
    """Read-only inline to show students linked to this parent"""

    model = StudentParent
    extra = 0
    can_delete = False
    fields = ["student", "relationship", "is_primary"]
    readonly_fields = ["student", "relationship", "is_primary"]

    def has_add_permission(self, request, obj=None):
        return False  # Can't add students from parent side


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    form = ParentAdminForm  # Use custom form with encryption
    list_display = [
        "parent_id",
        "get_name",
        "get_phone",
        "get_email",
        "get_students_count",
        "created_at",
    ]
    search_fields = ["parent_id", "phone", "email"]  # Enable autocomplete search
    readonly_fields = ["parent_id", "created_at"]
    inlines = [ParentStudentsInline]  # Show linked students

    # Disable add permission - parents should only be created via Student admin inline
    def has_add_permission(self, request):
        return False

    @display(description="Students")
    def get_students_count(self, obj):
        count = obj.student_parents.count()
        if count > 0:
            return format_html('<span style="color: green;">{} student(s)</span>', count)
        return format_html('<span style="color: orange;">No students linked</span>')

    @display(description="Name")
    def get_name(self, obj):
        try:
            return obj.encrypted_name
        except Exception:
            return obj.name

    @display(description="Phone")
    def get_phone(self, obj):
        try:
            return obj.encrypted_phone
        except Exception:
            return obj.phone

    @display(description="Email")
    def get_email(self, obj):
        try:
            return obj.encrypted_email
        except Exception:
            return obj.email


# StudentParent admin removed - use inline in Student admin instead
# This prevents accidental orphaned relationships and ensures data consistency
# @admin.register(StudentParent)
# class StudentParentAdmin(admin.ModelAdmin):
#     list_display = ["student", "parent", "relationship", "is_primary"]
#     list_filter = ["relationship", "is_primary"]
#     search_fields = ["student__name", "parent__name"]


@admin.register(FaceEmbeddingMetadata)
class FaceEmbeddingMetadataAdmin(admin.ModelAdmin):
    list_display = [
        "embedding_id",
        "get_student",
        "model_name",
        "quality_score",
        "is_primary",
        "embedding",
    ]
    list_filter = ["model_name", "is_primary"]
    search_fields = ["student_photo__student__name", "embedding"]
    readonly_fields = ["embedding_id", "embedding", "created_at"]

    @display(description="Student")
    def get_student(self, obj):
        return obj.student_photo.student
