from __future__ import annotations

from typing import Callable, Sequence

from django.conf import settings

from .definitions import EtlJobDefinition, default_job_definitions
from .runner import HourlyRunCoordinator


def create_coordinator(
    jobs: Sequence[EtlJobDefinition] | None = None,
    *,
    sleep: Callable[[float], None] | None = None,
) -> HourlyRunCoordinator:
    """Factory for HourlyRunCoordinator instances."""
    configured_jobs = jobs or default_job_definitions()
    max_workers = getattr(settings, "ETL_SCHEDULER_MAX_WORKERS", None)
    return HourlyRunCoordinator(
        configured_jobs,
        sleep=sleep,
        max_workers=max_workers,
    )
