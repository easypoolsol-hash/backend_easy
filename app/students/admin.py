from django.contrib import admin
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


class StudentPhotoInline(admin.TabularInline):
    model = StudentPhoto
    extra = 1  # Allow adding new photos inline
    fields = ["photo", "is_primary", "captured_at", "photo_preview"]
    readonly_fields = ["captured_at", "photo_preview"]

    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" width="100" height="100" />', obj.photo.url)
        return "No photo"

    photo_preview.short_description = "Preview"


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ["student_id", "get_name", "grade", "section", "assigned_bus", "status"]
    list_filter = ["status", "grade", "school"]
    search_fields = ["student_id", "name"]
    readonly_fields = ["student_id", "created_at", "updated_at"]
    inlines = [StudentPhotoInline]

    def get_name(self, obj):
        return obj.encrypted_name

    get_name.short_description = "Name"


class FaceEmbeddingInline(admin.TabularInline):
    model = FaceEmbeddingMetadata
    extra = 0
    fields = ["model_name", "quality_score", "is_primary", "qdrant_point_id"]
    readonly_fields = ["qdrant_point_id", "created_at"]


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

    def photo_thumbnail(self, obj):
        if obj.photo:
            return format_html('<img src="{}" width="50" height="50" />', obj.photo.url)
        return "No photo"

    photo_thumbnail.short_description = "Thumbnail"

    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" width="300" />', obj.photo.url)
        return "No photo"

    photo_preview.short_description = "Photo Preview"

    def embedding_count(self, obj):
        count = obj.face_embeddings.count()
        if count > 0:
            return format_html('<span style="color: green;">✓ {}</span>', count)
        return format_html('<span style="color: red;">✗ 0</span>')

    embedding_count.short_description = "Embeddings"


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ["parent_id", "get_name", "get_phone", "get_email", "created_at"]
    search_fields = ["phone", "email", "name"]
    readonly_fields = ["parent_id", "created_at"]

    def get_name(self, obj):
        return obj.encrypted_name

    get_name.short_description = "Name"

    def get_phone(self, obj):
        return obj.encrypted_phone

    get_phone.short_description = "Phone"

    def get_email(self, obj):
        return obj.encrypted_email

    get_email.short_description = "Email"


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
        "qdrant_point_id",
    ]
    list_filter = ["model_name", "is_primary"]
    search_fields = ["student_photo__student__name", "qdrant_point_id"]
    readonly_fields = ["embedding_id", "qdrant_point_id", "created_at"]

    def get_student(self, obj):
        return obj.student_photo.student

    get_student.short_description = "Student"
