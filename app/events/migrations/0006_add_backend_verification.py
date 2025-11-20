# Generated manually for backend multi-model verification

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0001_initial"),
        ("events", "0005_alter_boardingevent_student"),
    ]

    operations = [
        migrations.AddField(
            model_name="boardingevent",
            name="backend_verification_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending Verification"),
                    ("verified", "Verified"),
                    ("flagged", "Flagged for Review"),
                    ("failed", "Verification Failed"),
                ],
                default="pending",
                help_text="Backend multi-model verification status",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="boardingevent",
            name="backend_verification_confidence",
            field=models.CharField(
                blank=True,
                choices=[("high", "High Confidence"), ("medium", "Medium Confidence"), ("low", "Low Confidence")],
                help_text="Confidence level from backend verification consensus",
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="boardingevent",
            name="backend_student",
            field=models.ForeignKey(
                blank=True,
                help_text="Student identified by backend multi-model consensus (may differ from kiosk)",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="backend_verified_events",
                to="students.student",
            ),
        ),
        migrations.AddField(
            model_name="boardingevent",
            name="model_consensus_data",
            field=models.JSONField(blank=True, default=dict, help_text="Detailed results from all backend models (arcface, adaface, mobilefacenet)"),
        ),
        migrations.AddField(
            model_name="boardingevent",
            name="backend_verified_at",
            field=models.DateTimeField(blank=True, help_text="When backend verification completed", null=True),
        ),
        migrations.AddIndex(
            model_name="boardingevent",
            index=models.Index(fields=["backend_verification_status"], name="idx_events_verification_status"),
        ),
    ]
