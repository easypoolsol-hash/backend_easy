import csv
import os
import tempfile
import zipfile

from django import forms
from django.contrib import admin, messages
from django.contrib.admin import display
from django.db import transaction
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
        fields = [
            "user",
            "plaintext_name",
            "plaintext_phone",
            "plaintext_email",
            "approval_status",
            "approved_by",
            "approved_at",
        ]

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


class StudentPhotoInlineForm(forms.ModelForm):
    """Custom form to handle photo upload and convert to binary"""

    photo_upload = forms.ImageField(required=False, label="Upload Photo")

    class Meta:
        model = StudentPhoto
        fields = ["is_primary"]

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Convert uploaded file to binary data
        if self.cleaned_data.get("photo_upload"):
            uploaded_file = self.cleaned_data["photo_upload"]
            instance.photo_data = uploaded_file.read()
            instance.photo_content_type = uploaded_file.content_type or "image/jpeg"

        if commit:
            instance.save()
        return instance


class StudentPhotoInline(admin.TabularInline):
    model = StudentPhoto
    form = StudentPhotoInlineForm
    extra = 1  # Allow adding new photos inline
    fields = ["photo_upload", "is_primary", "photo_preview"]
    readonly_fields = ["photo_preview"]

    @display(description="Preview")
    def photo_preview(self, obj):
        if obj.photo_url:
            return format_html('<img src="{}" width="100" height="100" />', obj.photo_url)
        return NO_PHOTO


class StudentParentInline(admin.TabularInline):
    """Inline to link/unlink parents to student (parent details edited in Parent admin only)"""

    model = StudentParent
    extra = 1  # Allow adding parents (optional)
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


class BulkUploadForm(forms.Form):
    """Form for bulk student upload via ZIP file"""

    zip_file = forms.FileField(
        label="Upload ZIP file",
        help_text="ZIP containing: students.csv + student_folders/ with photos",
    )
    school = forms.ModelChoiceField(
        queryset=School.objects.all(),
        label="School",
        help_text="Select the school for all students",
    )


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    form = StudentAdminForm  # Use custom form with encryption
    list_display = [
        "school_student_id",
        "get_name",
        "grade",
        "section",
        "get_photo_count",
        "get_embedding_count",
        "get_primary_parent",
        "assigned_bus",
        "status",
    ]
    list_filter = ["status", "grade", "school"]
    search_fields = ["school_student_id", "student_id"]
    readonly_fields = ["student_id", "created_at", "updated_at"]
    inlines = [StudentParentInline, StudentPhotoInline]  # Parents first, then photos
    change_list_template = "admin/students/student_changelist.html"

    def get_queryset(self, request):
        """Optimize queryset with counts to avoid N+1 queries"""
        from django.db.models import Count

        qs = super().get_queryset(request)
        qs = qs.annotate(
            photo_count=Count("photos", distinct=True),
            embedding_count=Count("photos__face_embeddings", distinct=True),
        )
        return qs

    @display(description="Student Name")
    def get_name(self, obj):
        try:
            return obj.encrypted_name
        except Exception:
            # If decryption fails, return the raw name (likely not encrypted)
            return obj.name

    @display(description="Photos", ordering="photo_count")
    def get_photo_count(self, obj):
        """Display number of photos with status indicator"""
        count = getattr(obj, "photo_count", obj.photos.count())
        if count == 0:
            return format_html('<span style="color: red; font-weight: bold;">⚠️ 0</span>')
        elif count == 1:
            return format_html('<span style="color: orange;">📷 1</span>')
        else:
            return format_html('<span style="color: green;">📷 {}</span>', count)

    @display(description="Embeddings", ordering="embedding_count")
    def get_embedding_count(self, obj):
        """Display number of face embeddings with status indicator"""
        count = getattr(obj, "embedding_count", 0)
        if count == 0:
            return format_html('<span style="color: red; font-weight: bold;">⚠️ 0</span>')
        elif count < getattr(obj, "photo_count", obj.photos.count()):
            # Some photos don't have embeddings
            return format_html('<span style="color: orange;">🔍 {}</span>', count)
        else:
            return format_html('<span style="color: green;">🔍 {}</span>', count)

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

    def get_urls(self):
        from django.urls import path

        urls = super().get_urls()
        custom_urls = [
            path(
                "bulk-upload/",
                self.admin_site.admin_view(self.bulk_upload_view),
                name="students_student_bulk_upload",
            ),
        ]
        return custom_urls + urls

    def bulk_upload_view(self, request):
        """Handle bulk upload of students from ZIP file"""
        from django.shortcuts import redirect, render

        if request.method == "POST":
            form = BulkUploadForm(request.POST, request.FILES)
            if form.is_valid():
                zip_file = form.cleaned_data["zip_file"]
                school = form.cleaned_data["school"]

                try:
                    result = self._process_bulk_upload(zip_file, school)
                    messages.success(
                        request,
                        f"✅ Successfully imported {result['created']} students with {result['photos']} photos. "
                        f"Skipped {result['skipped']} existing students.",
                    )
                    return redirect("..")
                except Exception as e:
                    messages.error(request, f"❌ Upload failed: {e!s}")
        else:
            form = BulkUploadForm()

        context = {
            "form": form,
            "title": "Bulk Upload Students",
            "site_title": self.admin_site.site_title,
            "site_header": self.admin_site.site_header,
            "has_permission": True,
        }
        return render(request, "admin/students/bulk_upload.html", context)

    def _process_bulk_upload(self, zip_file, school):
        """Process uploaded ZIP file and create students"""
        created_count = 0
        photo_count = 0
        skipped_count = 0

        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract ZIP
            with zipfile.ZipFile(zip_file, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            # Find CSV file
            csv_path = None
            for root, _dirs, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith(".csv"):
                        csv_path = os.path.join(root, file)
                        break
                if csv_path:
                    break

            if not csv_path:
                raise ValueError("No CSV file found in ZIP")

            # Find student_folders directory
            folders_path = None
            for root, dirs, _files in os.walk(temp_dir):
                if "student_folders" in dirs:
                    folders_path = os.path.join(root, "student_folders")
                    break

            # Read CSV and create students
            with transaction.atomic():
                with open(csv_path, encoding="utf-8") as csvfile:
                    reader = csv.DictReader(csvfile)

                    for row in reader:
                        # Extract data (support both old and new headers)
                        adm_no = (row.get("admission_no") or row.get("Adm  No.", "")).strip()
                        name = (row.get("name") or row.get("Student Name", "")).strip()
                        class_section = (row.get("class_section") or row.get("Class Section", "")).strip()

                        if not adm_no or not name:
                            continue

                        # Parse class and section
                        grade = ""
                        section = ""
                        if class_section:
                            parts = class_section.split(" - ")
                            if len(parts) == 2:
                                grade = parts[0].strip()
                                section = parts[1].strip()
                            else:
                                grade = class_section

                        # Check if student exists
                        if Student.objects.filter(school_student_id=adm_no, school=school).exists():
                            skipped_count += 1
                            continue

                        # Create student
                        student = Student.objects.create(
                            school=school,
                            school_student_id=adm_no,
                            encrypted_name=name,
                            grade=grade,
                            section=section,
                            status="active",
                        )
                        created_count += 1

                        # Find and attach photos
                        if folders_path:
                            photo_count += self._attach_photos(student, folders_path, adm_no)

        return {"created": created_count, "photos": photo_count, "skipped": skipped_count}

    def _attach_photos(self, student, folders_path, adm_no):
        """Find photos in student_folders and attach to student"""
        photo_count = 0

        # Find folder starting with _{adm_no}_
        for folder_name in os.listdir(folders_path):
            if folder_name.startswith(f"_{adm_no}_"):
                folder_path = os.path.join(folders_path, folder_name)

                # Find all image files in folder
                for file_name in os.listdir(folder_path):
                    if file_name.lower().endswith((".jpg", ".jpeg", ".png")):
                        file_path = os.path.join(folder_path, file_name)

                        # Create StudentPhoto with binary data
                        with open(file_path, "rb") as photo_file:
                            photo_data = photo_file.read()

                            # Determine content type from file extension
                            content_type = "image/jpeg"
                            if file_name.lower().endswith(".png"):
                                content_type = "image/png"

                            StudentPhoto.objects.create(
                                student=student,
                                photo_data=photo_data,
                                photo_content_type=content_type,
                                is_primary=(photo_count == 0),  # First photo is primary
                            )
                            photo_count += 1

                break  # Found the folder, no need to continue

        return photo_count


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
        if obj.photo_url:
            return format_html('<img src="{}" width="50" height="50" />', obj.photo_url)
        return NO_PHOTO

    @display(description="Photo Preview")
    def photo_preview(self, obj):
        if obj.photo_url:
            return format_html('<img src="{}" width="300" />', obj.photo_url)
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
        "get_user",
        "approval_status_display",
        "get_students_count",
        "created_at",
    ]
    list_filter = ["approval_status", "created_at"]
    search_fields = ["parent_id", "phone", "email", "user__username", "user__email"]  # Enable autocomplete search
    readonly_fields = ["parent_id", "created_at", "updated_at", "approved_at"]
    inlines = [ParentStudentsInline]  # Show linked students
    actions = ["approve_parents", "reject_parents"]

    fieldsets = (
        ("Basic Information", {"fields": ("parent_id", "user", "plaintext_name", "plaintext_email", "plaintext_phone")}),
        ("Approval Status", {"fields": ("approval_status", "approved_by", "approved_at")}),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

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

    @display(description="User Account")
    def get_user(self, obj):
        if obj.user:
            return format_html(
                '<a href="/admin/users/user/{}/change/">{}</a>',
                obj.user.user_id,
                obj.user.username,
            )
        return format_html('<span style="color: red;">No user linked</span>')

    @display(description="Status")
    def approval_status_display(self, obj):
        if obj.approval_status == "approved":
            return format_html('<span style="color: green; font-weight: bold;">✓ Approved</span>')
        elif obj.approval_status == "rejected":
            return format_html('<span style="color: red; font-weight: bold;">✗ Rejected</span>')
        else:
            return format_html('<span style="color: orange; font-weight: bold;">⏳ Pending</span>')

    @admin.action(description="Approve selected parents")
    def approve_parents(self, request, queryset):
        """Bulk approve parents"""
        approved_count = 0
        for parent in queryset:
            try:
                parent.approve(request.user)
                approved_count += 1
            except ValueError as e:
                messages.error(request, f"Failed to approve {parent}: {e}")

        if approved_count > 0:
            messages.success(request, f"✓ Successfully approved {approved_count} parent(s)")

    @admin.action(description="Reject selected parents")
    def reject_parents(self, request, queryset):
        """Bulk reject parents"""
        rejected_count = 0
        for parent in queryset:
            try:
                parent.reject(request.user)
                rejected_count += 1
            except Exception as e:
                messages.error(request, f"Failed to reject {parent}: {e}")

        if rejected_count > 0:
            messages.success(request, f"✗ Rejected {rejected_count} parent(s)")


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
