"""Utilities for persisted ETL watermarks."""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Any, Mapping

from django.db import transaction
from django.utils import timezone

from .models import EtlJobWatermark


@dataclass(frozen=True)
class JobWatermark:
    """Lightweight representation of a stored watermark."""

    token: str | None
    timestamp: _dt.datetime | None
    metadata: Mapping[str, Any]


def _normalize_timestamp(value: _dt.date | _dt.datetime | None) -> _dt.datetime | None:
    if value is None:
        return None
    if isinstance(value, _dt.date) and not isinstance(value, _dt.datetime):
        value = _dt.datetime.combine(value, _dt.time.min)
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone=_dt.timezone.utc)
    return value


def get_watermark(job_name: str) -> JobWatermark:
    """Return the stored watermark for ``job_name`` (creating a stub if needed)."""

    record, _ = EtlJobWatermark.objects.get_or_create(job_name=job_name)
    return JobWatermark(record.last_token or None, record.last_timestamp, record.metadata)


@transaction.atomic
def update_watermark(
    job_name: str,
    *,
    token: str | None = None,
    timestamp: _dt.date | _dt.datetime | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> JobWatermark:
    """Persist the updated watermark, avoiding regressions."""

    record, _ = (
        EtlJobWatermark.objects.select_for_update().get_or_create(job_name=job_name)
    )
    fields_to_update: list[str] = []
    timestamp_updated = False

    normalized_ts = _normalize_timestamp(timestamp)
    if normalized_ts:
        if record.last_timestamp is None or normalized_ts > record.last_timestamp:
            record.last_timestamp = normalized_ts
            fields_to_update.append("last_timestamp")
            timestamp_updated = True

    if token:
        should_update_token = False
        if record.last_timestamp is None or timestamp_updated:
            should_update_token = True
        elif normalized_ts and record.last_timestamp == normalized_ts:
            should_update_token = token != record.last_token
        elif normalized_ts is None:
            should_update_token = token != record.last_token

        if should_update_token:
            record.last_token = token
            fields_to_update.append("last_token")

    if metadata:
        new_metadata = {**record.metadata, **metadata}
        if new_metadata != record.metadata:
            record.metadata = new_metadata
            fields_to_update.append("metadata")

    if fields_to_update:
        fields_to_update.append("updated_at")
        record.save(update_fields=fields_to_update)

    return JobWatermark(record.last_token or None, record.last_timestamp, record.metadata)


def should_process(
    job_name: str,
    *,
    token: str,
    timestamp: _dt.date | _dt.datetime,
    watermark: JobWatermark | None = None,
) -> bool:
    """Return ``True`` when the item exceeds the stored watermark."""

    watermark = watermark or get_watermark(job_name)
    normalized_ts = _normalize_timestamp(timestamp)
    if watermark.timestamp is None:
        return True
    if normalized_ts and normalized_ts > watermark.timestamp:
        return True
    return token != watermark.token
