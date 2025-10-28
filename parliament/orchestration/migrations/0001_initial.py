from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="EtlJobCheckpoint",
            fields=[
                ("id", models.AutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name="ID")),
                ("job_name", models.CharField(max_length=120, unique=True)),
                ("last_window_start", models.DateTimeField(blank=True, null=True)),
                ("last_started_at", models.DateTimeField(blank=True, null=True)),
                ("last_completed_at", models.DateTimeField(blank=True, null=True)),
                ("last_attempt", models.PositiveIntegerField(default=0)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("idle", "Idle"),
                            ("running", "Running"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                            ("skipped", "Skipped"),
                        ],
                        default="idle",
                        max_length=16,
                    ),
                ),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["job_name"]},
        ),
    ]
