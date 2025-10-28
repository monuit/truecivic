import datetime

from django.db import migrations
from django.utils import timezone


def _as_aware(date_value):
    dt = datetime.datetime.combine(date_value, datetime.time.min)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone=timezone.utc)
    return dt


def seed_initial_watermarks(apps, schema_editor):
    Watermark = apps.get_model("orchestration", "EtlJobWatermark")
    VoteQuestion = apps.get_model("bills", "VoteQuestion")
    Document = apps.get_model("hansards", "Document")

    latest_vote = VoteQuestion.objects.select_related("session").order_by("-date").first()
    if latest_vote and latest_vote.date:
        session = latest_vote.session
        token = f"{session.parliamentnum}:{session.sessnum}:{latest_vote.number}"
        timestamp = _as_aware(latest_vote.date)
        Watermark.objects.update_or_create(
            job_name="votes",
            defaults={
                "last_token": token,
                "last_timestamp": timestamp,
            },
        )

    latest_hansard = (
        Document.objects.filter(document_type="D", last_imported__isnull=False)
        .order_by("-last_imported")
        .first()
    )
    if latest_hansard:
        Watermark.objects.update_or_create(
            job_name="hansards",
            defaults={
                "last_token": str(latest_hansard.source_id),
                "last_timestamp": latest_hansard.last_imported,
            },
        )


def remove_initial_watermarks(apps, schema_editor):
    Watermark = apps.get_model("orchestration", "EtlJobWatermark")
    Watermark.objects.filter(job_name__in=["votes", "hansards"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("orchestration", "0003_etljobwatermark"),
        ("bills", "0001_initial"),
        ("hansards", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_initial_watermarks, remove_initial_watermarks),
    ]
