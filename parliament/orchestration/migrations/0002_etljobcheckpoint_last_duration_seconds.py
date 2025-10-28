from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orchestration", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="etljobcheckpoint",
            name="last_duration_seconds",
            field=models.FloatField(blank=True, null=True),
        ),
    ]
