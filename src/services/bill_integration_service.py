"""
Integration service for pipeline and database operations.

Coordinates fetching bills from adapters and persisting to database
with proper transaction management and error handling.

Responsibility: Integrate pipeline orchestration with database persistence
"""

from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING, Dict, Any
import logging

from ..orchestration.bill_pipeline import BillPipeline
from ..db.session import db
from ..db.repositories import BillRepository
from ..db.repositories.bill_repository import (
    BillPersistenceOutcome,
    BillPersistenceStatus,
)
from ..db.models import FetchLogModel
from ..models.adapter_models import AdapterStatus
from ..models.bill import Bill
from ..utils.hash_utils import compute_bill_hash, deduplicate_by_hash
from ..config.ingestion_defaults import MIN_BILL_INTRODUCED_DATE

if TYPE_CHECKING:
    from ..db.session import Database

logger = logging.getLogger(__name__)


class BillIntegrationService:
    """
    Integration service for bill data pipeline and persistence.

    Orchestrates the complete flow:
    1. Fetch bills from OpenParliament/LEGISinfo via pipeline
    2. Persist bills to database via repository
    3. Log fetch operations for monitoring

    Example:
        # With async context manager (recommended)
        async with BillIntegrationService(db) as service:
            result = await service.fetch_and_persist(
                parliament=44,
                session=1,
                limit=100,
                enrich=True
            )

        # Or without context manager
        service = BillIntegrationService()
        result = await service.fetch_and_persist(limit=100)
        await service.close()
    """

    def __init__(self, database: Optional["Database"] = None):
        """
        Initialize integration service.

        Args:
            database: Optional Database instance (if None, uses global db)
        """
        self.database = database
        self.pipeline = BillPipeline(
            enrich_by_default=True,
            max_enrichment_errors=10
        )

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
        return False

    async def fetch_and_persist(
        self,
        parliament: Optional[int] = None,
        session: Optional[int] = None,
        limit: int = 100,
        enrich: bool = True,
        introduced_after: Optional[datetime] = None,
        introduced_before: Optional[datetime] = None,
        **kwargs
    ) -> dict:
        """
        Fetch bills from pipeline and persist to database.

        Args:
            parliament: Filter by parliament number
            session: Filter by session number
            limit: Maximum bills to fetch
            enrich: Whether to enrich with LEGISinfo
            **kwargs: Additional parameters

        Returns:
            Dict with results:
                - fetched_count: Number of bills fetched
                - persisted_count: Number of bills persisted
                - updated_count: Number of bills updated
                - created_count: Number of bills created
                - errors: List of error messages
                - status: Overall status
        """
        start_time = datetime.utcnow()

        logger.info(
            "Starting fetch and persist: parliament=%s, session=%s, limit=%s, enrich=%s, "
            "introduced_after=%s, introduced_before=%s",
            parliament,
            session,
            limit,
            enrich,
            introduced_after,
            introduced_before,
        )

        if introduced_after and introduced_after.tzinfo:
            introduced_after = introduced_after.astimezone(
                timezone.utc).replace(tzinfo=None)
        if introduced_before and introduced_before.tzinfo:
            introduced_before = introduced_before.astimezone(
                timezone.utc).replace(tzinfo=None)

        try:
            # Stage 1: Fetch bills via pipeline
            logger.info("Fetching bills from pipeline...")

            pipeline_response = await self.pipeline.fetch_and_enrich(
                parliament=parliament,
                session=session,
                limit=limit,
                enrich=enrich,
                introduced_after=introduced_after,
                introduced_before=introduced_before
            )

            raw_bills = pipeline_response.data or []
            bills, duplicates_skipped = deduplicate_by_hash(
                raw_bills, compute_bill_hash)
            if duplicates_skipped:
                logger.info(
                    "Deduplicated %d bills from pipeline payload via content hash",
                    duplicates_skipped,
                )
            else:
                duplicates_skipped = 0

            filtered_bills: List[Bill] = []
            filtered_out = 0
            for bill in bills:
                introduced_date = bill.introduced_date
                if introduced_date and introduced_date < MIN_BILL_INTRODUCED_DATE:
                    filtered_out += 1
                    continue
                filtered_bills.append(bill)

            if filtered_out:
                logger.info(
                    "Filtered out %d bills introduced before %s",
                    filtered_out,
                    MIN_BILL_INTRODUCED_DATE.date(),
                )

            bills = filtered_bills

            introduced_dates = [
                bill.introduced_date for bill in bills if bill.introduced_date]
            earliest_introduced = min(
                introduced_dates) if introduced_dates else None
            latest_introduced = max(
                introduced_dates) if introduced_dates else None

            logger.info(
                "Pipeline fetch complete: %d bills, status=%s",
                len(bills),
                pipeline_response.status.value,
            )

            # Stage 2: Persist bills to database
            logger.info("Persisting bills to database...")

            created_count = 0
            updated_count = 0
            unchanged_count = 0
            persist_errors = []
            persistence_outcomes: List[BillPersistenceOutcome] = []

            if bills:
                # Use the database instance from __init__ if provided, otherwise use global
                database_to_use = self.database if self.database else db

                async with database_to_use.session() as session_db:
                    repo = BillRepository(session_db)

                    try:
                        persistence_outcomes = await repo.upsert_many(bills)

                        for outcome in persistence_outcomes:
                            if outcome.status == BillPersistenceStatus.CREATED:
                                created_count += 1
                            elif outcome.status == BillPersistenceStatus.UPDATED:
                                updated_count += 1
                            else:
                                unchanged_count += 1

                        logger.info(
                            "Persistence summary: %d created, %d updated, %d unchanged",
                            created_count,
                            updated_count,
                            unchanged_count,
                        )

                    except Exception as e:
                        logger.error(
                            f"Database persistence error: {e}", exc_info=True)
                        persist_errors.append(str(e))

            # Stage 3: Log fetch operation
            duration = (datetime.utcnow() - start_time).total_seconds()

            # Use the database instance from __init__ if provided, otherwise use global
            database_to_use = self.database if self.database else db

            result_summary: Dict[str, Any] = {
                "fetched": len(raw_bills),
                "after_filters": len(bills),
                "persisted": created_count + updated_count,
                "created": created_count,
                "updated": updated_count,
                "unchanged": unchanged_count,
                "duplicates_skipped": duplicates_skipped,
                "filtered_pre_2015": filtered_out,
                "max_introduced_date": latest_introduced.isoformat() if latest_introduced else None,
                "min_introduced_date": earliest_introduced.isoformat() if earliest_introduced else None,
            }

            async with database_to_use.session() as session_db:
                await self._log_fetch_operation(
                    session_db=session_db,
                    source="bill_integration_service",
                    status=pipeline_response.status.value,
                    records_attempted=len(raw_bills),
                    records_succeeded=created_count + updated_count,
                    records_failed=len(
                        pipeline_response.errors) + len(persist_errors),
                    duration_seconds=duration,
                    fetch_params={
                        "parliament": parliament,
                        "session": session,
                        "limit": limit,
                        "enrich": enrich,
                        "introduced_after": introduced_after.isoformat() if introduced_after else None,
                        "introduced_before": introduced_before.isoformat() if introduced_before else None,
                    },
                    result_summary=result_summary,
                    errors=pipeline_response.errors + [
                        {"message": err} for err in persist_errors
                    ]
                )

            logger.info("Fetch operation logged successfully")

            # Build result
            result = {
                "raw_bills_fetched": len(raw_bills),
                "bills_fetched": len(bills),
                "persisted_count": created_count + updated_count,
                "created": created_count,
                "updated": updated_count,
                "unchanged": unchanged_count,
                "duplicates_skipped": duplicates_skipped,
                "filtered_pre_2015": filtered_out,
                "errors": [
                    err.message for err in pipeline_response.errors
                ] + persist_errors,
                "error_count": len(pipeline_response.errors) + len(persist_errors),
                "status": pipeline_response.status.value,
                "duration_seconds": duration,
                "max_introduced_date": latest_introduced.isoformat() if latest_introduced else None,
                "min_introduced_date": earliest_introduced.isoformat() if earliest_introduced else None,
            }

            logger.info(
                "Fetch and persist complete: %d persisted, %d unchanged, "
                "%d duplicates skipped, %d errors",
                result['persisted_count'],
                unchanged_count,
                duplicates_skipped,
                len(result['errors']),
            )

            return result

        except Exception as e:
            logger.error(f"Integration service error: {e}", exc_info=True)

            # Log failed operation
            duration = (datetime.utcnow() - start_time).total_seconds()

            try:
                # Use the database instance from __init__ if provided, otherwise use global
                database_to_use = self.database if self.database else db

                async with database_to_use.session() as session_db:
                    await self._log_fetch_operation(
                        session_db=session_db,
                        source="bill_integration_service",
                        status="failure",
                        records_attempted=limit,
                        records_succeeded=0,
                        records_failed=limit,
                        duration_seconds=duration,
                        fetch_params={
                            "parliament": parliament,
                            "session": session,
                            "limit": limit,
                            "enrich": enrich,
                            "introduced_after": introduced_after.isoformat() if introduced_after else None,
                            "introduced_before": introduced_before.isoformat() if introduced_before else None,
                        },
                        result_summary=None,
                        errors=[{"message": str(e)}]
                    )
            except Exception as log_error:
                logger.error(f"Failed to log error: {log_error}")

            raise

    async def _log_fetch_operation(
        self,
        session_db,
        source: str,
        status: str,
        records_attempted: int,
        records_succeeded: int,
        records_failed: int,
        duration_seconds: float,
        fetch_params: dict,
        result_summary: Optional[Dict[str, Any]] = None,
        errors: Optional[List] = None
    ) -> None:
        """
        Log fetch operation to database.

        Args:
            session_db: Database session
            source: Source identifier
            status: Operation status
            records_attempted: Number of records attempted
            records_succeeded: Number of records succeeded
            records_failed: Number of records failed
            duration_seconds: Operation duration
            fetch_params: Fetch parameters
            result_summary: Optional dictionary with additional metrics
            errors: List of errors
        """
        params_payload: Dict[str, Any] = dict(fetch_params or {})
        if result_summary:
            params_payload["result_summary"] = result_summary

        error_items = errors or []

        error_payload: List[Dict[str, Any]] = []
        for err in error_items[:10]:
            if hasattr(err, "timestamp") and hasattr(err, "message"):
                error_payload.append(
                    {
                        "timestamp": err.timestamp.isoformat(),
                        "type": getattr(err, "error_type", type(err).__name__),
                        "message": err.message,
                    }
                )
            elif isinstance(err, dict):
                error_payload.append(
                    {
                        "timestamp": err.get("timestamp")
                        or datetime.utcnow().isoformat(),
                        "type": err.get("type")
                        or err.get("error_type")
                        or "unknown",
                        "message": err.get("message", str(err)),
                    }
                )
            else:
                error_payload.append(
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "type": type(err).__name__,
                        "message": str(err),
                    }
                )

        fetch_log = FetchLogModel(
            source=source,
            status=status,
            records_attempted=records_attempted,
            records_succeeded=records_succeeded,
            records_failed=records_failed,
            duration_seconds=duration_seconds,
            fetch_params=params_payload,
            error_count=len(error_items),
            error_summary=error_payload,
        )

        session_db.add(fetch_log)
        await session_db.flush()

    async def close(self):
        """Close pipeline and cleanup resources"""
        await self.pipeline.close()
        logger.info("Integration service closed")
