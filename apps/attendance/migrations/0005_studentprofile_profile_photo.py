from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0004_leaverequest_supervisorassignment"),
        ("media_assets", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentprofile",
            name="profile_photo",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="student_profile_photo",
                to="media_assets.mediaasset",
                verbose_name="foto profil",
            ),
        ),
    ]
