from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orchestration", "0002_etljobcheckpoint_last_duration_seconds"),
    ]

    operations = [
        migrations.CreateModel(
            name="EtlJobWatermark",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("job_name", models.CharField(max_length=120, unique=True)),
                ("last_token", models.CharField(blank=True, max_length=255)),
                (
                    "last_timestamp",
                    models.DateTimeField(blank=True, null=True),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["job_name"],
            },
        ),
    ]
