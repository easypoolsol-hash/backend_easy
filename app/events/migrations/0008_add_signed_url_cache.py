# Generated manually for adding signed URL cache fields to BoardingEvent

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0007_boardingevent_backend_config_version"),
    ]

    operations = [
        migrations.AddField(
            model_name="boardingevent",
            name="confirmation_face_1_signed_url",
            field=models.TextField(blank=True, default="", help_text="Cached signed URL for first confirmation face (7-day expiry)"),
        ),
        migrations.AddField(
            model_name="boardingevent",
            name="confirmation_face_1_url_expires_at",
            field=models.DateTimeField(blank=True, help_text="When the cached signed URL for face 1 expires", null=True),
        ),
        migrations.AddField(
            model_name="boardingevent",
            name="confirmation_face_2_signed_url",
            field=models.TextField(blank=True, default="", help_text="Cached signed URL for second confirmation face (7-day expiry)"),
        ),
        migrations.AddField(
            model_name="boardingevent",
            name="confirmation_face_2_url_expires_at",
            field=models.DateTimeField(blank=True, help_text="When the cached signed URL for face 2 expires", null=True),
        ),
        migrations.AddField(
            model_name="boardingevent",
            name="confirmation_face_3_signed_url",
            field=models.TextField(blank=True, default="", help_text="Cached signed URL for third confirmation face (7-day expiry)"),
        ),
        migrations.AddField(
            model_name="boardingevent",
            name="confirmation_face_3_url_expires_at",
            field=models.DateTimeField(blank=True, help_text="When the cached signed URL for face 3 expires", null=True),
        ),
    ]
