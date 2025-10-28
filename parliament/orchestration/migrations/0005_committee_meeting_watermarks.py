import datetime

from django.db import migrations
from django.utils import timezone


def _as_aware(date_value, time_value):
    if not date_value:
        return None
    base_time = time_value or datetime.time.min
    dt = datetime.datetime.combine(date_value, base_time)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone=timezone.utc)
    return dt


def seed_committee_watermarks(apps, schema_editor):
    Watermark = apps.get_model("orchestration", "EtlJobWatermark")
    CommitteeMeeting = apps.get_model("committees", "CommitteeMeeting")

    meetings = (
        CommitteeMeeting.objects.select_related("committee", "session")
        .order_by("session_id", "committee_id", "-date", "-start_time")
    )
    seen_keys = set()
    for meeting in meetings:
        key = (meeting.session_id, meeting.committee_id)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        timestamp = _as_aware(meeting.date, meeting.start_time)
        token = (
            str(meeting.source_id)
            if meeting.source_id
            else f"{meeting.session_id}:{meeting.committee_id}:{meeting.number}"
        )
        job_name = f"committee_meetings.{meeting.session_id}.{meeting.committee_id}"
        metadata = {
            "session_id": meeting.session_id,
            "committee_id": meeting.committee_id,
            "number": meeting.number,
            "source_id": meeting.source_id,
            "date": meeting.date.isoformat() if meeting.date else None,
        }
        defaults = {"last_token": token, "metadata": metadata}
        if timestamp:
            defaults["last_timestamp"] = timestamp
        Watermark.objects.update_or_create(job_name=job_name, defaults=defaults)


def remove_committee_watermarks(apps, schema_editor):
    Watermark = apps.get_model("orchestration", "EtlJobWatermark")
    Watermark.objects.filter(job_name__startswith="committee_meetings.").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("orchestration", "0004_populate_watermarks"),
        ("committees", "0002_committee_joint"),
    ]

    operations = [
        migrations.RunPython(seed_committee_watermarks, remove_committee_watermarks),
    ]
