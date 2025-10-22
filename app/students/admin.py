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


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = [
        "student_id",
        "get_name",
        "grade",
        "section",
        "assigned_bus",
        "status",
    ]
    list_filter = ["status", "grade", "school"]
    search_fields = ["student_id", "name"]
    readonly_fields = ["student_id", "created_at", "updated_at"]
    inlines = [StudentPhotoInline]

    def save_model(self, request, obj, form, change):
        # Auto-encrypt name if plaintext entered
        if "name" in form.changed_data:
            obj.name = obj.name  # Setter encrypts automatically
        super().save_model(request, obj, form, change)

    @display(description="Name")
    def get_name(self, obj):
        try:
            return obj.encrypted_name
        except Exception:
            # If decryption fails, return the raw name (likely not encrypted)
            return obj.name


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


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = [
        "parent_id",
        "get_name",
        "get_phone",
        "get_email",
        "created_at",
    ]
    search_fields = ["phone", "email", "name"]
    readonly_fields = ["parent_id", "created_at"]

    def save_model(self, request, obj, form, change):
        # Auto-encrypt fields if plaintext entered
        if "name" in form.changed_data:
            obj.name = obj.name  # Setter encrypts
        if "phone" in form.changed_data:
            obj.phone = obj.phone  # Setter encrypts
        if "email" in form.changed_data:
            obj.email = obj.email  # Setter encrypts
        super().save_model(request, obj, form, change)

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


@admin.register(StudentParent)
class StudentParentAdmin(admin.ModelAdmin):
    list_display = ["student", "parent", "relationship", "is_primary"]
    list_filter = ["relationship", "is_primary"]
    search_fields = ["student__name", "parent__name"]


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
