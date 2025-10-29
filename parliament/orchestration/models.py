from __future__ import annotations

from django.db import models


class EtlJobWatermark(models.Model):
    """Persisted high-water mark for incremental ETL jobs."""

    job_name = models.CharField(max_length=120, unique=True)
    last_token = models.CharField(max_length=255, blank=True)
    last_timestamp = models.DateTimeField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["job_name"]

    def __str__(self) -> str:
        token = self.last_token or "<unset>"
        ts = self.last_timestamp.isoformat() if self.last_timestamp else "<unset>"
        return f"{self.job_name} watermark token={token} ts={ts}"


class EtlJobCheckpoint(models.Model):
    """Checkpoint status for an ETL job within an hourly window."""

    class Status(models.TextChoices):
        IDLE = "idle", "Idle"
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    job_name = models.CharField(max_length=120, unique=True)
    last_window_start = models.DateTimeField(blank=True, null=True)
    last_started_at = models.DateTimeField(blank=True, null=True)
    last_completed_at = models.DateTimeField(blank=True, null=True)
    last_attempt = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.IDLE,
    )
    last_error = models.TextField(blank=True)
    last_duration_seconds = models.FloatField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["job_name"]

    def __str__(self) -> str:
        window = self.last_window_start.isoformat() if self.last_window_start else "pending"
        return f"{self.job_name} ({self.status}) @ {window}"

    @property
    def has_completed(self) -> bool:
        return self.status in {self.Status.SUCCESS, self.Status.SKIPPED}
