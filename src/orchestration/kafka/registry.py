"""Kafka job registry utilities."""

from __future__ import annotations

from typing import Iterable

from parliament import jobs


def iter_job_names() -> Iterable[str]:
    """Yield callable job names defined in parliament.jobs."""
    for name in dir(jobs):
        job = getattr(jobs, name)
        if callable(job) and not name.startswith("_"):
            yield name
