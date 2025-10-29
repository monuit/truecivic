from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Tuple


@dataclass(frozen=True)
class EtlJobDefinition:
    """Configuration describing how an ETL job is executed."""

    name: str
    func: Callable[[], None]
    max_attempts: int = 2
    retry_delay_seconds: float = 60.0
    dependencies: Tuple[str, ...] = ()


def default_job_definitions() -> Tuple[EtlJobDefinition, ...]:
    """Return the ordered list of ETL jobs executed each hour."""
    from parliament import jobs as job_module

    return (
        EtlJobDefinition("mps", job_module.mps, max_attempts=2),
        EtlJobDefinition(
            "votes",
            job_module.votes,
            max_attempts=3,
            dependencies=("mps",),
        ),
        EtlJobDefinition("bills", job_module.bills, max_attempts=2),
        EtlJobDefinition("hansards", job_module.hansards, max_attempts=3),
        EtlJobDefinition("committees", job_module.committees, max_attempts=2),
        EtlJobDefinition(
            "committee_evidence",
            job_module.committee_evidence,
            max_attempts=2,
            dependencies=("committees",),
        ),
        EtlJobDefinition(
            "summaries",
            job_module.summaries,
            max_attempts=2,
            dependencies=("hansards",),
        ),
        EtlJobDefinition(
            "rag_ingest",
            job_module.rag_ingest,
            max_attempts=2,
            dependencies=(
                "mps",
                "votes",
                "bills",
                "hansards",
                "committees",
                "committee_evidence",
                "summaries",
            ),
        ),
    )
