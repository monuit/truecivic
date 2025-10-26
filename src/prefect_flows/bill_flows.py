"""
Prefect flows for Parliament Explorer bill ingestion pipeline.

Defines flows for:
- Fetching bills from OpenParliament API
- Enriching bills with LEGISinfo data
- Persisting bills to database
- Monitoring fetch operations

Responsibility: Orchestrate periodic bill data refreshes
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

from prefect import flow, task, get_run_logger
from prefect.tasks import task_input_hash

from src.services.bill_integration_service import BillIntegrationService
from src.db.session import Database
from src.db.repositories.fetch_log_repository import FetchLogRepository
from src.config.ingestion_defaults import (
    BILL_FETCH_WINDOW_DAYS,
    MIN_BILL_INTRODUCED_DATE,
)
from src.prefect_flows.constants import (
    PREFECT_CONCURRENCY_TAG_API,
    PREFECT_CONCURRENCY_TAG_DB,
    PREFECT_RESULT_STORAGE_BLOCK,
)


def _string_to_datetime(value: Any) -> Optional[datetime]:
    """Best-effort conversion of ISO8601-like strings to ``datetime`` objects."""

    if value is None or isinstance(value, datetime):
        return value

    if isinstance(value, str):
        try:
            cleaned = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(cleaned)
            if parsed.tzinfo:
                return parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
        except ValueError:
            return None

    return None


async def _derive_introduced_after(
    db: Database,
    *,
    explicit_after: Optional[datetime],
    parliament: Optional[int],
    session: Optional[int],
) -> datetime:
    """Determine the floor for the fetch window respecting historical bounds."""

    if explicit_after:
        return max(explicit_after, MIN_BILL_INTRODUCED_DATE)

    repo = FetchLogRepository(db)
    params = await repo.get_last_successful_bill_window(
        parliament=parliament,
        session_filter=session,
    )
    if params:
        candidate = _string_to_datetime(params.get("max_introduced_date"))
        if candidate:
            return max(candidate, MIN_BILL_INTRODUCED_DATE)

    # Fall back to decade window ending today
    fallback = datetime.utcnow() - timedelta(days=BILL_FETCH_WINDOW_DAYS)
    return max(fallback, MIN_BILL_INTRODUCED_DATE)


@task(
    name="fetch_bills",
    description="Fetch bills from OpenParliament and enrich with LEGISinfo",
    retries=5,
    retry_delay_seconds=60,
    retry_jitter_factor=0.3,
    cache_key_fn=task_input_hash,
    cache_expiration=timedelta(minutes=10),
    persist_result=True,
    result_storage=PREFECT_RESULT_STORAGE_BLOCK,
    result_serializer="json",
    tags={PREFECT_CONCURRENCY_TAG_API, PREFECT_CONCURRENCY_TAG_DB},
)
async def fetch_bills_task(
    limit: int = 50,
    parliament: Optional[int] = None,
    session: Optional[int] = None,
    introduced_after: Optional[datetime] = None,
    introduced_before: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Fetch bills from OpenParliament, enrich with LEGISinfo, and persist to database.

    Args:
        limit: Maximum number of bills to fetch
        parliament: Specific parliament number (None for all)
        session: Specific session number (None for all)

    Returns:
        Dictionary with operation statistics
    """
    logger = get_run_logger()
    logger.info(
        "Starting bill fetch: limit=%s, parliament=%s, session=%s, introduced_after=%s, introduced_before=%s",
        limit,
        parliament,
        session,
        introduced_after,
        introduced_before,
    )

    # Normalize timezone-aware inputs to naive UTC for consistent comparisons
    if introduced_after and introduced_after.tzinfo:
        introduced_after = introduced_after.astimezone(
            timezone.utc).replace(tzinfo=None)
    if introduced_before and introduced_before.tzinfo:
        introduced_before = (
            introduced_before.astimezone(timezone.utc).replace(tzinfo=None)
        )

    # Initialize database and integration service
    db = Database()
    await db.initialize()

    effective_after = await _derive_introduced_after(
        db,
        explicit_after=introduced_after,
        parliament=parliament,
        session=session,
    )

    effective_before = (
        max(introduced_before, MIN_BILL_INTRODUCED_DATE)
        if introduced_before
        else None
    )

    if effective_before is not None and effective_before <= effective_after:
        logger.warning(
            "Introduced-before constraint %s is before derived window %s; ignoring upper bound",
            effective_before,
            effective_after,
        )
        effective_before = None

    try:
        async with BillIntegrationService(db) as service:
            logger.info(
                "Fetching %s bills from OpenParliament API (window %s - %s)...",
                limit,
                effective_after.isoformat(),
                effective_before.isoformat() if effective_before else "present",
            )

            result = await service.fetch_and_persist(
                limit=limit,
                parliament=parliament,
                session=session,
                introduced_after=effective_after,
                introduced_before=effective_before,
            )

            logger.info(
                "Fetch complete: fetched=%s persisted=%s (created=%s updated=%s) "
                "unchanged=%s duplicates=%s errors=%s",
                result.get("bills_fetched", 0),
                result.get("persisted_count", 0),
                result.get("created", 0),
                result.get("updated", 0),
                result.get("unchanged", 0),
                result.get("duplicates_skipped", 0),
                result.get("error_count", 0),
            )

            return result
    finally:
        await db.close()


@task(
    name="monitor_fetch_operations",
    description="Monitor fetch operations and report statistics",
    retries=2,
    retry_delay_seconds=30,
    retry_jitter_factor=0.2,
    persist_result=True,
    result_storage=PREFECT_RESULT_STORAGE_BLOCK,
    result_serializer="json",
    tags={"monitoring"},
)
async def monitor_fetch_operations_task(hours_back: int = 24) -> Dict[str, Any]:
    """
    Monitor fetch operations from the last N hours and report statistics.

    Args:
        hours_back: Number of hours to look back

    Returns:
        Dictionary with monitoring statistics
    """
    logger = get_run_logger()
    logger.info(f"Monitoring fetch operations for last {hours_back} hours...")

    db = Database()
    await db.initialize()

    try:
        # Query fetch_logs table for monitoring
        repo = FetchLogRepository(db)

        # Get logs from last N hours
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        logs = await repo.get_logs_since(cutoff_time)

        # Calculate statistics
        total_operations = len(logs)
        successful = sum(1 for log in logs if log.status == "success")
        failed = sum(1 for log in logs if log.status == "error")
        partial = sum(1 for log in logs if log.status == "partial")

        avg_duration = (
            sum(log.duration_seconds for log in logs) / total_operations
            if total_operations > 0
            else 0
        )

        persisted_total = 0
        duplicates_total = 0
        filtered_total = 0
        latest_max_introduced: Optional[datetime] = None

        for log_entry in logs:
            params = log_entry.fetch_params or {}
            summary = params.get("result_summary") if isinstance(
                params, dict) else {}
            if isinstance(summary, dict):
                persisted_total += int(summary.get("persisted", 0) or 0)
                duplicates_total += int(summary.get("duplicates_skipped", 0) or 0)
                filtered_total += int(summary.get("filtered_pre_2015", 0) or 0)
                max_date = _string_to_datetime(
                    summary.get("max_introduced_date"))
                if max_date and (latest_max_introduced is None or max_date > latest_max_introduced):
                    latest_max_introduced = max_date

        stats = {
            "total_operations": total_operations,
            "successful": successful,
            "failed": failed,
            "partial": partial,
            "avg_duration_seconds": round(avg_duration, 2),
            "success_rate": round(successful / total_operations * 100, 2) if total_operations > 0 else 0,
            "records_persisted": persisted_total,
            "duplicates_skipped": duplicates_total,
            "filtered_pre_2015": filtered_total,
            "latest_introduced_at": latest_max_introduced.isoformat() if latest_max_introduced else None,
        }

        logger.info(f"Monitoring stats: {stats}")
        return stats

    finally:
        await db.close()


@flow(
    name="fetch-latest-bills",
    description="Fetch latest bills from OpenParliament and LEGISinfo",
    log_prints=True,
    persist_result=True,
    result_storage=PREFECT_RESULT_STORAGE_BLOCK,
    result_serializer="json",
)
async def fetch_latest_bills_flow(
    limit: int = 50,
    introduced_after: Optional[datetime] = None,
    introduced_before: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Main flow for fetching latest bills.

    This flow:
    1. Fetches bills from OpenParliament API (most recent first)
    2. Enriches with LEGISinfo data (status, summaries, sponsor names)
    3. Upserts into database (creates new, updates existing)
    4. Logs operation for monitoring

    Args:
        limit: Maximum number of bills to fetch (default 50)

    Returns:
        Operation statistics
    """
    logger = get_run_logger()
    logger.info(
        f"🏛️ Starting Parliament Explorer bill fetch flow (limit={limit})")

    # Fetch bills
    result = await fetch_bills_task(
        limit=limit,
        introduced_after=introduced_after,
        introduced_before=introduced_before,
    )

    logger.info(
        f"✅ Flow complete: {result['bills_fetched']} bills processed, "
        f"{result['created']} created, {result['updated']} updated"
    )

    return result


@flow(
    name="fetch-parliament-session-bills",
    description="Fetch all bills from a specific parliament and session",
    log_prints=True,
    persist_result=True,
    result_storage=PREFECT_RESULT_STORAGE_BLOCK,
    result_serializer="json",
)
async def fetch_parliament_session_bills_flow(
    parliament: int,
    session: int,
    limit: int = 1000,
    introduced_after: Optional[datetime] = None,
    introduced_before: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Backfill flow for fetching all bills from a specific parliament and session.

    Args:
        parliament: Parliament number (e.g., 44)
        session: Session number (e.g., 1)
        limit: Maximum number of bills to fetch (default 1000)

    Returns:
        Operation statistics
    """
    logger = get_run_logger()
    logger.info(
        f"🏛️ Backfilling bills for Parliament {parliament}, Session {session}")

    # Fetch bills for specific parliament/session
    result = await fetch_bills_task(
        limit=limit,
        parliament=parliament,
        session=session,
        introduced_after=introduced_after,
        introduced_before=introduced_before,
    )

    logger.info(
        f"✅ Backfill complete for P{parliament}S{session}: "
        f"{result['bills_fetched']} bills processed"
    )

    return result


@flow(
    name="monitor-fetch-operations",
    description="Monitor fetch operations and report statistics",
    log_prints=True,
    persist_result=True,
    result_storage=PREFECT_RESULT_STORAGE_BLOCK,
    result_serializer="json",
)
async def monitor_fetch_operations_flow(hours_back: int = 24) -> Dict[str, Any]:
    """
    Monitoring flow for fetch operations.

    Args:
        hours_back: Number of hours to look back (default 24)

    Returns:
        Monitoring statistics
    """
    logger = get_run_logger()
    logger.info(f"📊 Monitoring fetch operations (last {hours_back} hours)")

    # Get monitoring stats
    stats = await monitor_fetch_operations_task(hours_back=hours_back)

    logger.info(
        f"✅ Monitoring complete: {stats['total_operations']} operations, "
        f"{stats['success_rate']}% success rate"
    )

    return stats


@flow(
    name="fetch-bills",
    description="Fetch bills with optional date filters",
    log_prints=True,
    persist_result=True,
    result_storage=PREFECT_RESULT_STORAGE_BLOCK,
    result_serializer="json",
)
async def fetch_bills_flow(
    parliament: Optional[int] = None,
    session: Optional[int] = None,
    limit: int = 100,
    introduced_after: Optional[datetime] = None,
    introduced_before: Optional[datetime] = None,
) -> Dict[str, Any]:
    """General-purpose flow for fetching bills with optional filters."""
    logger = get_run_logger()
    logger.info(
        "🏛️ Fetching bills (parliament=%s, session=%s, limit=%s, introduced_after=%s, introduced_before=%s)",
        parliament,
        session,
        limit,
        introduced_after,
        introduced_before,
    )

    result = await fetch_bills_task(
        limit=limit,
        parliament=parliament,
        session=session,
        introduced_after=introduced_after,
        introduced_before=introduced_before,
    )

    logger.info(
        "✅ Fetch complete: %s bills processed (created=%s, updated=%s)",
        result.get("bills_fetched", 0),
        result.get("created", 0),
        result.get("updated", 0),
    )

    return result


if __name__ == "__main__":
    import asyncio

    # Test the flow locally
    asyncio.run(fetch_latest_bills_flow(limit=10))
