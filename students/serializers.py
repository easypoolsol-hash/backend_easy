from rest_framework import serializers

from buses.models import Bus
from .models import (
    FaceEmbeddingMetadata,
    Parent,
    School,
    Student,
    StudentParent,
    StudentPhoto,
)


class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = ['school_id', 'name', 'created_at']
        read_only_fields = ['school_id', 'created_at']


class BusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bus
        fields = [
            'bus_id', 'license_plate', 'capacity', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['bus_id', 'created_at', 'updated_at']


class StudentPhotoSerializer(serializers.ModelSerializer):
    student_details = serializers.SerializerMethodField()

    class Meta:
        model = StudentPhoto
        fields = [
            'photo_id', 'student', 'photo_url', 'is_primary', 'captured_at',
            'student_details', 'created_at'
        ]
        read_only_fields = ['photo_id', 'created_at']

    def get_student_details(self, obj):
        return {
            'student_id': obj.student.student_id,
            'name': obj.student.encrypted_name,
            'grade': obj.student.grade
        }


class ParentSerializer(serializers.ModelSerializer):
    # Decrypted fields for API responses
    decrypted_name = serializers.SerializerMethodField()
    decrypted_phone = serializers.SerializerMethodField()
    decrypted_email = serializers.SerializerMethodField()

    class Meta:
        model = Parent
        fields = [
            'parent_id', 'decrypted_name', 'decrypted_phone',
            'decrypted_email', 'name', 'phone', 'email', 'created_at'
        ]
        read_only_fields = ['parent_id', 'created_at']

    def get_decrypted_name(self, obj):
        return obj.encrypted_name

    def get_decrypted_phone(self, obj):
        return obj.encrypted_phone

    def get_decrypted_email(self, obj):
        return obj.encrypted_email

    def create(self, validated_data):
        # Encrypt PII fields before saving
        parent = Parent()
        parent.encrypted_name = validated_data.get('name', '')
        parent.encrypted_phone = validated_data.get('phone', '')
        parent.encrypted_email = validated_data.get('email', '')
        parent.save()
        return parent

    def update(self, instance, validated_data):
        # Update encrypted fields
        if 'name' in validated_data:
            instance.encrypted_name = validated_data['name']
        if 'phone' in validated_data:
            instance.encrypted_phone = validated_data['phone']
        if 'email' in validated_data:
            instance.encrypted_email = validated_data['email']
        instance.save()
        return instance


class StudentParentSerializer(serializers.ModelSerializer):
    parent_details = ParentSerializer(source='parent', read_only=True)
    student_details = serializers.SerializerMethodField()

    class Meta:
        model = StudentParent
        fields = [
            'student', 'parent', 'relationship', 'is_primary',
            'parent_details', 'student_details'
        ]

    def get_student_details(self, obj):
        return {
            'student_id': obj.student.student_id,
            'name': obj.student.encrypted_name,
            'grade': obj.student.grade,
            'section': obj.student.section
        }


class StudentSerializer(serializers.ModelSerializer):
    # Decrypted name for API responses
    decrypted_name = serializers.SerializerMethodField()
    school_details = SchoolSerializer(source='school', read_only=True)
    bus_details = BusSerializer(source='assigned_bus', read_only=True)
    parents = serializers.SerializerMethodField()
    photos = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            'student_id', 'school', 'decrypted_name', 'name', 'grade',
            'section', 'assigned_bus', 'status', 'enrollment_date',
            'school_details', 'bus_details', 'parents', 'photos',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['student_id', 'created_at', 'updated_at']

    def get_decrypted_name(self, obj):
        return obj.encrypted_name

    def get_parents(self, obj):
        student_parents = obj.student_parents.select_related('parent').all()
        return StudentParentSerializer(student_parents, many=True).data

    def get_photos(self, obj):
        photos = obj.photos.all().order_by('-is_primary', '-captured_at')
        return StudentPhotoSerializer(photos, many=True).data

    def create(self, validated_data):
        # Encrypt name before saving
        student = Student()
        student.school = validated_data['school']
        student.encrypted_name = validated_data.get('name', '')
        student.grade = validated_data['grade']
        student.section = validated_data.get('section', '')
        student.assigned_bus = validated_data.get('assigned_bus')
        student.status = validated_data.get('status', 'active')
        student.enrollment_date = validated_data['enrollment_date']
        student.save()
        return student

    def update(self, instance, validated_data):
        # Update encrypted name if provided
        if 'name' in validated_data:
            instance.encrypted_name = validated_data['name']
        # Update other fields
        for attr in [
            'school', 'grade', 'section', 'assigned_bus',
            'status', 'enrollment_date'
        ]:
            if attr in validated_data:
                setattr(instance, attr, validated_data[attr])
        instance.save()
        return instance


class FaceEmbeddingMetadataSerializer(serializers.ModelSerializer):
    student_details = serializers.SerializerMethodField()
    photo_details = serializers.SerializerMethodField()

    class Meta:
        model = FaceEmbeddingMetadata
        fields = [
            'embedding_id', 'student_photo', 'model_name', 'model_version',
            'qdrant_point_id', 'quality_score', 'is_primary', 'captured_at',
            'student_details', 'photo_details', 'created_at'
        ]
        read_only_fields = ['embedding_id', 'created_at']

    def get_student_details(self, obj):
        return {
            'student_id': obj.student_photo.student.student_id,
            'name': obj.student_photo.student.encrypted_name,
            'grade': obj.student_photo.student.grade
        }

    def get_photo_details(self, obj):
        return {
            'photo_id': obj.student_photo.photo_id,
            'photo_url': obj.student_photo.photo_url,
            'is_primary': obj.student_photo.is_primary,
            'captured_at': obj.student_photo.captured_at
        }
