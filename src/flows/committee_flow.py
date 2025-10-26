"""
Prefect flow for fetching and storing committee data.

Orchestrates the committee adapter to fetch parliamentary committee information.
"""
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

from prefect import flow, task, get_run_logger
from prefect.task_runners import ConcurrentTaskRunner
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.committee_adapter import CommitteeAdapter
from src.db.session import async_session_factory
from src.db.repositories.committee_repository import CommitteeRepository
from src.db.repositories.committee_meeting_repository import CommitteeMeetingRepository
from src.models.adapter_models import CommitteeData, CommitteeMeetingData, AdapterStatus
from src.utils.committee_registry import build_committee_identifier, resolve_source_slug

logger = logging.getLogger(__name__)


@task(name="fetch_committees", retries=2, retry_delay_seconds=30)
async def fetch_committees_task(parliament: int, session: int, limit: int = 100) -> List[CommitteeData]:
    """
    Fetch committees for a parliament session.

    Args:
        parliament: Parliament number
        session: Session number
        limit: Results per page

    Returns:
        List of CommitteeData objects
    """
    logger = get_run_logger()
    logger.info(
        f"Fetching committees for Parliament {parliament}, Session {session}")

    adapter = CommitteeAdapter()
    try:
        response = await adapter.fetch_committees_for_session(parliament, session, limit)
    finally:
        await adapter.close()

    if response.errors:
        for error in response.errors:
            logger.warning(
                "Committee fetch error (%s): %s", error.error_type, error.message
            )

    committees = response.data or []
    logger.info(
        "Fetched %s committees (status=%s, not_modified=%s)",
        len(committees),
        response.status.value,
        response.metadata.get("not_modified"),
    )

    if response.status != AdapterStatus.SUCCESS:
        logger.warning(
            "Committee fetch completed with status %s; errors=%s",
            response.status.value,
            len(response.errors),
        )

    return committees


@task(name="fetch_all_committees", retries=2, retry_delay_seconds=30)
async def fetch_all_committees_task(limit: int = 100) -> List[CommitteeData]:
    """
    Fetch all committees across all sessions.

    Args:
        limit: Results per page

    Returns:
        List of CommitteeData objects
    """
    logger = get_run_logger()
    logger.info(f"Fetching all committees")

    adapter = CommitteeAdapter()
    try:
        response = await adapter.fetch_all_committees(limit)
    finally:
        await adapter.close()

    if response.errors:
        for error in response.errors:
            logger.warning(
                "Committee fetch error (%s): %s", error.error_type, error.message
            )

    committees = response.data or []
    logger.info(
        "Fetched %s total committees (status=%s, not_modified=%s)",
        len(committees),
        response.status.value,
        response.metadata.get("not_modified"),
    )

    if response.status != AdapterStatus.SUCCESS:
        logger.warning(
            "Full committee fetch completed with status %s; errors=%s",
            response.status.value,
            len(response.errors),
        )

    return committees


@task(name="store_committees", retries=1)
async def store_committees_task(committees: List[CommitteeData]) -> int:
    """
    Store committees in the database.

    Args:
        committees: List of CommitteeData objects

    Returns:
        Number of committees stored
    """
    logger = get_run_logger()
    logger.info(f"Storing {len(committees)} committees in database")

    stored_count = 0

    if not committees:
        logger.info("No committee records received")
        return 0

    async with async_session_factory() as session:
        repository = CommitteeRepository(session)
        payloads: List[Dict[str, Any]] = []

        canonical_jurisdiction = "ca-federal"

        for committee_data in committees:
            try:
                identifier_seed = (
                    committee_data.committee_slug
                    or committee_data.acronym_en
                    or committee_data.acronym_fr
                    or committee_data.committee_id
                )
                identifier = build_committee_identifier(identifier_seed)

                parliament = committee_data.parliament
                session = committee_data.session

                if parliament is None or session is None:
                    raise ValueError(
                        "Committee payload missing parliament/session metadata")

                name_en = committee_data.name_en or identifier.code
                name_fr = committee_data.name_fr or name_en
                source_slug = committee_data.source_slug or identifier.source_slug
                source_url = committee_data.source_url

                parliament_value = int(parliament)
                session_value = int(session)

                if not source_url and source_slug:
                    source_url = f"https://api.openparliament.ca/committees/{source_slug}/"
                if not source_url:
                    source_url = (
                        f"https://www.ourcommons.ca/Committees/en/{identifier.code}"
                        f"?parl={parliament_value}&session={session_value}"
                    )

                acronym_en = (
                    committee_data.acronym_en or identifier.code).upper()
                acronym_fr = (committee_data.acronym_fr or acronym_en).upper()
                short_name_en = committee_data.short_name_en or name_en
                short_name_fr = committee_data.short_name_fr or name_fr or short_name_en

                natural_id = (
                    f"{canonical_jurisdiction}-{parliament_value}-{session_value}-committee-{identifier.code}"
                )

                payloads.append(
                    {
                        "natural_id": natural_id,
                        "jurisdiction": canonical_jurisdiction,
                        "parliament": parliament_value,
                        "session": session_value,
                        "committee_code": identifier.code,
                        "committee_slug": identifier.internal_slug,
                        "source_slug": source_slug,
                        "name_en": name_en,
                        "name_fr": name_fr,
                        "chamber": committee_data.chamber or "House",
                        "acronym_en": acronym_en,
                        "acronym_fr": acronym_fr,
                        "short_name_en": short_name_en,
                        "short_name_fr": short_name_fr,
                        "parent_committee": committee_data.parent_committee,
                        "source_url": source_url,
                        "committee_type": None,
                        "website_url": None,
                    }
                )
            except Exception as exc:
                logger.error(
                    "Failed to prepare committee payload %s: %s",
                    committee_data.committee_id,
                    exc,
                )

        if not payloads:
            logger.warning(
                "All committee payloads failed validation; nothing stored")
            return 0

        async with session.begin():
            stored_committees = await repository.upsert_many(payloads)
            stored_count = len(stored_committees)

    logger.info(f"Stored {stored_count} committees")
    return stored_count


@task(name="fetch_committee_meetings", retries=2, retry_delay_seconds=30)
async def fetch_committee_meetings_task(
    committee_identifiers: List[str],
    parliament: int,
    session_number: int,
    limit_per_committee: int = 50,
    include_details: bool = True,
) -> List[CommitteeMeetingData]:
    """Fetch meeting records for a set of committees."""

    logger_task = get_run_logger()
    if not committee_identifiers:
        logger_task.info("No committees provided for meeting fetch")
        return []

    adapter = CommitteeAdapter()
    unique_meetings: Dict[tuple, CommitteeMeetingData] = {}

    try:
        for identifier in committee_identifiers:
            response = await adapter.fetch_committee_meetings(
                committee_identifier=identifier,
                parliament=parliament,
                session=session_number,
                limit=limit_per_committee,
                include_details=include_details,
            )

            if response.errors:
                for error in response.errors:
                    logger_task.warning(
                        "Meeting fetch error (%s) for %s: %s",
                        error.error_type,
                        identifier,
                        error.message,
                    )

            meetings = response.data or []
            logger_task.info(
                "Fetched %s meetings for %s (parl=%s session=%s)",
                len(meetings),
                identifier,
                parliament,
                session_number,
            )

            for meeting in meetings:
                if meeting.meeting_number is None:
                    logger_task.warning(
                        "Skipping meeting without number for %s", identifier
                    )
                    continue

                key = (
                    meeting.committee_slug,
                    meeting.meeting_number,
                    meeting.parliament,
                    meeting.session,
                )
                unique_meetings[key] = meeting

    finally:
        await adapter.close()

    logger_task.info(
        "Prepared %s unique meetings for storage", len(unique_meetings)
    )
    return list(unique_meetings.values())


@task(name="store_committee_meetings", retries=1)
async def store_committee_meetings_task(
    meetings: List[CommitteeMeetingData],
) -> int:
    """Persist normalized meeting records."""

    logger_task = get_run_logger()
    if not meetings:
        logger_task.info("No meetings to store")
        return 0

    async with async_session_factory() as session:
        meeting_repository = CommitteeMeetingRepository(session)
        committee_repository = CommitteeRepository(session)

        slug_to_id: Dict[str, Optional[int]] = {}
        sanitized: List[Dict[str, Any]] = []

        for meeting in meetings:
            slug = meeting.committee_slug
            if slug not in slug_to_id:
                committee = await committee_repository.get_by_slug(slug)
                if committee is None:
                    committee = await committee_repository.get_by_code(
                        "ca-federal",
                        meeting.committee_code,
                    )
                slug_to_id[slug] = committee.id if committee else None

            committee_id = slug_to_id.get(slug)
            if not committee_id:
                logger_task.warning(
                    "Skipping meeting %s-%s: committee not found",
                    slug,
                    meeting.meeting_number,
                )
                continue

            if meeting.meeting_date is None:
                logger_task.warning(
                    "Skipping meeting %s-%s without meeting_date",
                    slug,
                    meeting.meeting_number,
                )
                continue

            sanitized.append(
                {
                    "committee_id": committee_id,
                    "meeting_number": meeting.meeting_number,
                    "parliament": meeting.parliament,
                    "session": meeting.session,
                    "meeting_date": meeting.meeting_date,
                    "time_of_day": meeting.time_of_day,
                    "title_en": meeting.title_en,
                    "title_fr": meeting.title_fr,
                    "meeting_type": meeting.meeting_type,
                    "room": meeting.room,
                    "witnesses": meeting.witnesses,
                    "documents": meeting.documents,
                    "source_url": meeting.source_url,
                }
            )

        if not sanitized:
            logger_task.info("All meetings filtered out during sanitation")
            return 0

        async with session.begin():
            stored = await meeting_repository.upsert_many(sanitized)
            count = len(stored)

    logger_task.info("Stored %s committee meetings", count)
    return count


@flow(
    name="fetch_committees",
    description="Fetch and store parliamentary committee data",
    task_runner=ConcurrentTaskRunner(),
    log_prints=True
)
async def fetch_committees_flow(
    parliament: int = 44,
    session: int = 1,
    limit: int = 100
) -> dict:
    """
    Main flow to fetch and store committee data for a specific session.

    Args:
        parliament: Parliament number (default: 44)
        session: Session number (default: 1)
        limit: Results per page (default: 100)

    Returns:
        Dictionary with flow results
    """
    logger = get_run_logger()
    logger.info(f"Starting committee fetch flow for {parliament}-{session}")

    start_time = datetime.utcnow()

    # Fetch committees
    committees = await fetch_committees_task(parliament, session, limit)

    # Store committees
    stored_count = await store_committees_task(committees)

    end_time = datetime.utcnow()
    duration = (end_time - start_time).total_seconds()

    result = {
        "status": "success",
        "parliament": parliament,
        "session": session,
        "committees_fetched": len(committees),
        "committees_stored": stored_count,
        "duration_seconds": duration,
        "timestamp": end_time.isoformat()
    }

    logger.info(f"Committee fetch flow completed: {result}")
    return result


@flow(
    name="fetch_committee_meetings",
    description="Fetch and store committee meeting data",
    task_runner=ConcurrentTaskRunner(),
    log_prints=True,
)
async def fetch_committee_meetings_flow(
    committee_identifiers: List[str],
    parliament: int = 44,
    session: int = 1,
    limit_per_committee: int = 50,
    include_details: bool = True,
) -> dict:
    """Flow orchestrating meeting ingestion for the supplied committees."""

    logger = get_run_logger()
    logger.info(
        "Starting committee meeting flow (%s committees, parl=%s, session=%s)",
        len(committee_identifiers),
        parliament,
        session,
    )

    start_time = datetime.utcnow()

    meetings = await fetch_committee_meetings_task(
        committee_identifiers=committee_identifiers,
        parliament=parliament,
        session_number=session,
        limit_per_committee=limit_per_committee,
        include_details=include_details,
    )

    stored_count = await store_committee_meetings_task(meetings)

    end_time = datetime.utcnow()
    duration = (end_time - start_time).total_seconds()

    result = {
        "status": "success" if stored_count or meetings else "no_data",
        "committees_processed": len(committee_identifiers),
        "meetings_fetched": len(meetings),
        "meetings_stored": stored_count,
        "duration_seconds": duration,
        "timestamp": end_time.isoformat(),
    }

    logger.info("Committee meeting flow completed: %s", result)
    return result


@flow(
    name="fetch_all_committees",
    description="Fetch and store all parliamentary committees",
    task_runner=ConcurrentTaskRunner(),
    log_prints=True
)
async def fetch_all_committees_flow(limit: int = 100) -> dict:
    """
    Fetch and store all committees across all sessions.

    Args:
        limit: Results per page (default: 100)

    Returns:
        Dictionary with flow results
    """
    logger = get_run_logger()
    logger.info(f"Starting all committees fetch flow")

    start_time = datetime.utcnow()

    # Fetch all committees
    committees = await fetch_all_committees_task(limit)

    # Store committees
    stored_count = await store_committees_task(committees)

    end_time = datetime.utcnow()
    duration = (end_time - start_time).total_seconds()

    result = {
        "status": "success",
        "committees_fetched": len(committees),
        "committees_stored": stored_count,
        "duration_seconds": duration,
        "timestamp": end_time.isoformat()
    }

    logger.info(f"All committees fetch flow completed: {result}")
    return result


if __name__ == "__main__":
    # Run the flow for testing
    asyncio.run(fetch_all_committees_flow(limit=100))
