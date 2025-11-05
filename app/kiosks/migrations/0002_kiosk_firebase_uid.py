# Generated manually for firebase_uid field

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("kiosks", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="kiosk",
            name="firebase_uid",
            field=models.CharField(
                blank=True, help_text="Firebase UID for this kiosk user (from Firebase Authentication)", max_length=128, null=True, unique=True
            ),
        ),
    ]
