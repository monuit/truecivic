"""
Enhanced Prefect flow for fetching votes with individual MP voting records.

Orchestrates vote data fetching and storage including individual ballot records.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional, Set
import logging

from prefect import flow, task, get_run_logger
from prefect.task_runners import ConcurrentTaskRunner

from src.adapters.openparliament_votes import OpenParliamentVotesAdapter
from sqlalchemy import select

from src.db.session import async_session_factory
from src.db.repositories.vote_repository import VoteRepository, VoteRecordRepository
from src.db.models import PoliticianModel, BillModel, VoteModel, VoteRecordModel
from src.utils import dedupe_by_key
from src.prefect_flows.constants import (
    PREFECT_CONCURRENCY_TAG_API,
    PREFECT_CONCURRENCY_TAG_DB,
    PREFECT_RESULT_STORAGE_BLOCK,
)

logger = logging.getLogger(__name__)


@task(
    name="fetch_votes_batch",
    retries=4,
    retry_delay_seconds=30,
    retry_jitter_factor=0.2,
    persist_result=True,
    result_storage=PREFECT_RESULT_STORAGE_BLOCK,
    result_serializer="json",
    tags={PREFECT_CONCURRENCY_TAG_API},
)
async def fetch_votes_batch_task(
    parliament: int,
    session: Optional[int],
    limit: int = 100,
    start_date: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch votes for a parliament session.

    Args:
        parliament: Parliament number
        session: Session number (optional)
        limit: Maximum votes to fetch

    Returns:
        List of vote dictionaries
    """
    logger_task = get_run_logger()
    session_label = f"{parliament}-{session}" if session is not None else f"{parliament}-all"
    logger_task.info(f"Fetching votes for Parliament/Session {session_label}")

    adapter = OpenParliamentVotesAdapter()
    response = await adapter.fetch(
        limit=limit,
        parliament=parliament,
        session=session
    )

    if response.errors:
        logger_task.error(f"Errors fetching votes: {response.errors}")

    records = response.data or []

    window_start = start_date or datetime.utcnow() - timedelta(days=3650)

    filtered: List[Dict[str, Any]] = []
    for vote in records:
        vote_date = vote.get("vote_date")
        parsed_date: Optional[datetime]
        if isinstance(vote_date, str):
            try:
                parsed_date = datetime.fromisoformat(
                    vote_date.replace("Z", "+00:00"))
            except ValueError:
                parsed_date = None
        elif isinstance(vote_date, datetime):
            parsed_date = vote_date
        else:
            parsed_date = None

        if parsed_date is None or parsed_date < window_start:
            continue

        vote["vote_date"] = parsed_date
        filtered.append(vote)

    filtered, duplicates = dedupe_by_key(filtered, lambda v: v.get("vote_id"))
    if duplicates:
        logger_task.warning("Removed %s duplicate votes", duplicates)

    logger_task.info(f"Fetched {len(filtered)} votes after filtering")
    return filtered


@task(
    name="fetch_vote_records_for_vote",
    retries=4,
    retry_delay_seconds=30,
    retry_jitter_factor=0.3,
    persist_result=True,
    result_storage=PREFECT_RESULT_STORAGE_BLOCK,
    result_serializer="json",
    tags={PREFECT_CONCURRENCY_TAG_API},
)
async def fetch_vote_records_task(vote_id: str) -> List[Dict[str, Any]]:
    """
    Fetch individual MP voting records for a specific vote.

    Args:
        vote_id: Vote identifier (e.g., '44-1-123')

    Returns:
        List of vote record dictionaries
    """
    logger_task = get_run_logger()
    logger_task.info(f"Fetching vote records for: {vote_id}")

    adapter = OpenParliamentVotesAdapter()
    response = await adapter.fetch_vote_by_id(vote_id)

    if response.errors:
        logger_task.error(f"Errors fetching vote records: {response.errors}")
        return []

    # Extract MP votes from the response
    records = response.data or []
    if records:
        vote_data = records[0]
        mp_votes = vote_data.get("mp_votes", [])
        mp_votes, duplicates = dedupe_by_key(
            mp_votes, lambda r: r.get("politician_id"))
        if duplicates:
            logger_task.warning(
                "Removed %s duplicate MP vote records for %s", duplicates, vote_id
            )
        logger_task.info(f"Fetched {len(mp_votes)} vote records for {vote_id}")
        return mp_votes

    return []


@task(
    name="store_votes_batch",
    retries=2,
    retry_delay_seconds=15,
    retry_jitter_factor=0.2,
    persist_result=True,
    result_storage=PREFECT_RESULT_STORAGE_BLOCK,
    result_serializer="json",
    tags={PREFECT_CONCURRENCY_TAG_DB},
)
async def store_votes_batch_task(votes_data: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Store votes in database using batch upsert.

    Args:
        votes_data: List of vote dictionaries

    Returns:
        Dict with counts of created/updated votes
    """
    logger_task = get_run_logger()
    logger_task.info(f"Storing {len(votes_data)} votes")

    if not votes_data:
        return {"created": 0, "updated": 0}

    votes_data, duplicates = dedupe_by_key(
        votes_data, lambda v: v.get("vote_id"))
    if duplicates:
        logger_task.warning(
            "Removed %s duplicate votes before storage", duplicates)

    async with async_session_factory() as session:
        vote_repo = VoteRepository(session)
        allowed_keys = {
            "jurisdiction",
            "vote_id",
            "parliament",
            "session",
            "vote_number",
            "chamber",
            "vote_date",
            "vote_description_en",
            "vote_description_fr",
            "result",
            "yeas",
            "nays",
            "abstentions",
            "created_at",
            "updated_at",
        }

        sanitized_votes: List[Dict[str, Any]] = []
        vote_ids: Set[str] = set()
        for vote in votes_data:
            sanitized = {k: v for k, v in vote.items() if k in allowed_keys}
            sanitized.setdefault("jurisdiction", "ca")
            sanitized.setdefault("created_at", datetime.utcnow())
            sanitized["updated_at"] = datetime.utcnow()

            vote_identifier = sanitized.get("vote_id")
            if isinstance(vote_identifier, str):
                vote_ids.add(vote_identifier)

            vote_date = sanitized.get("vote_date")
            if vote_date is None:
                sanitized["vote_date"] = datetime.utcnow()

            bill_id = None
            bill_number = vote.get("bill_number")
            if bill_number:
                result = await session.execute(
                    select(BillModel.id).where(BillModel.number == bill_number)
                )
                bill_id = result.scalar_one_or_none()
            sanitized["bill_id"] = bill_id

            sanitized_votes.append(sanitized)

        existing_vote_ids: Set[str] = set()
        if vote_ids:
            existing_stmt = select(VoteModel.vote_id).where(
                VoteModel.jurisdiction == "ca",
                VoteModel.vote_id.in_(vote_ids),
            )
            existing_result = await session.execute(existing_stmt)
            existing_vote_ids = {row[0] for row in existing_result}

        # Use batch upsert
        stored_votes = await vote_repo.upsert_many(sanitized_votes)
        await session.commit()

        created_count = sum(
            1
            for vote in sanitized_votes
            if not vote.get("vote_id") or vote.get("vote_id") not in existing_vote_ids
        )
        updated_count = max(len(stored_votes) - created_count, 0)

        logger_task.info(
            "Stored %s votes (created=%s, updated=%s)",
            len(stored_votes),
            created_count,
            updated_count,
        )

        return {
            "stored": len(stored_votes),
            "created": created_count,
            "updated": updated_count,
        }


@task(
    name="store_vote_records_batch",
    retries=2,
    retry_delay_seconds=15,
    retry_jitter_factor=0.2,
    persist_result=True,
    result_storage=PREFECT_RESULT_STORAGE_BLOCK,
    result_serializer="json",
    tags={PREFECT_CONCURRENCY_TAG_DB},
)
async def store_vote_records_batch_task(
    vote_id: str,
    vote_db_id: int,
    records_data: List[Dict[str, Any]]
) -> int:
    """
    Store vote records in database using batch upsert.

    Args:
        vote_id: Vote identifier
        vote_db_id: Vote database ID
        records_data: List of vote record dictionaries with politician_id and vote_position

    Returns:
        Count of stored records
    """
    logger_task = get_run_logger()
    logger_task.info(
        f"Storing {len(records_data)} vote records for vote {vote_id}")

    if not records_data:
        return 0

    async with async_session_factory() as session:
        vote_record_repo = VoteRecordRepository(session)

        # Map OpenParliament politician IDs to our database IDs and deduplicate
        records_map: Dict[int, Dict[str, Any]] = {}

        for record in records_data:
            op_politician_id = record.get("politician_id")
            if not op_politician_id:
                continue

            result = await session.execute(
                select(PoliticianModel.id).where(
                    PoliticianModel.id == op_politician_id)
            )
            politician_id = result.scalar_one_or_none()
            if not politician_id:
                logger_task.warning(
                    "Skipping vote record for politician %s (not found in database)",
                    op_politician_id,
                )
                continue

            records_map[politician_id] = {
                "vote_id": vote_db_id,
                "politician_id": politician_id,
                "vote_position": record.get("vote_position", "Unknown"),
                "created_at": datetime.utcnow(),
            }

        records_to_insert = list(records_map.values())

        if not records_to_insert:
            return 0

        existing_stmt = select(VoteRecordModel.politician_id).where(
            VoteRecordModel.vote_id == vote_db_id,
            VoteRecordModel.politician_id.in_(
                [r["politician_id"] for r in records_to_insert]),
        )
        existing_result = await session.execute(existing_stmt)
        existing_politicians = {row[0] for row in existing_result}

        stored_records = await vote_record_repo.upsert_many(records_to_insert)
        await session.commit()

        created_count = sum(
            1 for record in records_to_insert if record["politician_id"] not in existing_politicians
        )
        updated_count = max(len(stored_records) - created_count, 0)

        logger_task.info(
            "Stored %s vote records for vote %s (created=%s, updated=%s)",
            len(stored_records),
            vote_id,
            created_count,
            updated_count,
        )
        return len(stored_records)


@task(
    name="get_vote_db_id",
    persist_result=True,
    result_storage=PREFECT_RESULT_STORAGE_BLOCK,
    result_serializer="json",
    tags={PREFECT_CONCURRENCY_TAG_DB},
)
async def get_vote_db_id_task(jurisdiction: str, vote_id: str) -> int:
    """
    Get database ID for a vote by its natural key.

    Args:
        jurisdiction: Jurisdiction code
        vote_id: Vote identifier

    Returns:
        Database ID or None
    """
    async with async_session_factory() as session:
        vote_repo = VoteRepository(session)
        vote = await vote_repo.get_by_vote_id(jurisdiction, vote_id)
        return vote.id if vote else None


@flow(
    name="fetch_votes_with_records",
    description="Fetch votes and individual MP voting records",
    task_runner=ConcurrentTaskRunner(),
    log_prints=True,
    persist_result=True,
    result_storage=PREFECT_RESULT_STORAGE_BLOCK,
    result_serializer="json",
)
async def fetch_votes_with_records_flow(
    parliament: int = 45,
    session: Optional[int] = None,
    limit: int = 100,
    fetch_records: bool = True,
    start_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Main flow to fetch and store votes with optional individual MP records.

    Args:
        parliament: Parliament number (default: 45)
        session: Session number (default: all sessions)
        limit: Maximum votes to fetch (default: 100)
        fetch_records: Whether to fetch individual MP voting records (default: True)
        start_date: Earliest vote date to include (defaults to 10-year window)

    Returns:
        Dictionary with flow results
    """
    logger_flow = get_run_logger()
    session_label = f"{parliament}-{session}" if session is not None else f"{parliament}-all"
    logger_flow.info(f"Starting votes+records flow for {session_label}")

    start_time = datetime.utcnow()

    # Step 1: Fetch votes
    votes_data = await fetch_votes_batch_task(
        parliament=parliament,
        session=session,
        limit=limit,
        start_date=start_date,
    )

    if not votes_data:
        return {
            "status": "no_data",
            "votes_fetched": 0,
            "votes_stored": 0,
            "records_stored": 0
        }

    # Step 2: Store votes
    store_result = await store_votes_batch_task(votes_data)

    # Step 3: Optionally fetch and store individual MP vote records
    total_records = 0
    if fetch_records:
        logger_flow.info(
            f"Fetching individual vote records for {len(votes_data)} votes")

        # Limit to first 10 for now (API rate limits)
        for vote_data in votes_data[:10]:
            vote_id = vote_data.get("vote_id")
            if not vote_id:
                continue

            # Get database ID for this vote
            vote_db_id = await get_vote_db_id_task("ca", vote_id)
            if not vote_db_id:
                logger_flow.warning(f"Could not find DB ID for vote {vote_id}")
                continue

            # Fetch records for this vote
            records_data = await fetch_vote_records_task(vote_id)

            # Store records
            if records_data:
                stored_count = await store_vote_records_batch_task(
                    vote_id,
                    vote_db_id,
                    records_data
                )
                total_records += stored_count

    end_time = datetime.utcnow()
    duration = (end_time - start_time).total_seconds()

    result = {
        "status": "success",
        "parliament": parliament,
        "session": session,
        "votes_fetched": len(votes_data),
        "votes_stored": store_result.get("stored", 0),
        "records_stored": total_records,
        "duration_seconds": duration,
        "timestamp": end_time.isoformat()
    }

    logger_flow.info(f"Votes+records flow completed: {result}")
    return result


@flow(
    name="fetch_latest_votes_hourly",
    description="Hourly flow to fetch latest votes with records",
    task_runner=ConcurrentTaskRunner(),
    log_prints=True,
    persist_result=True,
    result_storage=PREFECT_RESULT_STORAGE_BLOCK,
    result_serializer="json",
)
async def fetch_latest_votes_hourly_flow(
    limit: int = 50,
    start_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Hourly scheduled flow to fetch the most recent votes.

    Args:
        limit: Maximum votes to fetch (default: 50)

    Returns:
        Dictionary with flow results
    """
    logger_flow = get_run_logger()
    logger_flow.info(f"Starting hourly latest votes flow (limit: {limit})")

    start_time = datetime.utcnow()

    # Fetch latest votes (no filters, just latest)
    adapter = OpenParliamentVotesAdapter()
    response = await adapter.fetch(limit=limit)

    if response.errors:
        logger_flow.error(f"Errors fetching votes: {response.errors}")
        return {"status": "error", "errors": response.errors}

    records = response.data or []

    window_start = start_date or datetime.utcnow() - timedelta(days=3650)

    filtered: List[Dict[str, Any]] = []
    for vote in records:
        vote_date = vote.get("vote_date")
        parsed_date: Optional[datetime]
        if isinstance(vote_date, str):
            try:
                parsed_date = datetime.fromisoformat(
                    vote_date.replace("Z", "+00:00"))
            except ValueError:
                parsed_date = None
        elif isinstance(vote_date, datetime):
            parsed_date = vote_date
        else:
            parsed_date = None

        if parsed_date is None or parsed_date < window_start:
            continue

        vote["vote_date"] = parsed_date
        filtered.append(vote)

    filtered, duplicates = dedupe_by_key(filtered, lambda v: v.get("vote_id"))
    if duplicates:
        logger_flow.warning(
            "Removed %s duplicate votes in hourly flow", duplicates)

    # Store votes
    store_result = await store_votes_batch_task(filtered)

    # Fetch records for recent votes (first 20)
    total_records = 0
    for vote_data in filtered[:20]:
        vote_id = vote_data.get("vote_id")
        if vote_id:
            vote_db_id = await get_vote_db_id_task("ca", vote_id)
            if vote_db_id:
                records_data = await fetch_vote_records_task(vote_id)
                if records_data:
                    stored_count = await store_vote_records_batch_task(
                        vote_id,
                        vote_db_id,
                        records_data
                    )
                    total_records += stored_count

    end_time = datetime.utcnow()
    duration = (end_time - start_time).total_seconds()

    result = {
        "status": "success",
        "votes_fetched": len(filtered),
        "votes_stored": store_result.get("stored", 0),
        "records_stored": total_records,
        "duration_seconds": duration,
        "timestamp": end_time.isoformat()
    }

    logger_flow.info(f"Hourly latest votes flow completed: {result}")
    return result


if __name__ == "__main__":
    # Test the flow
    asyncio.run(fetch_votes_with_records_flow(
        parliament=44, session=1, limit=10))
