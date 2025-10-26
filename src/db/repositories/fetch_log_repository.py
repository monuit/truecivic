"""
Repository for FetchLog database operations.

Handles CRUD operations for fetch operation logs, used for monitoring
pipeline health and performance.
"""

from datetime import datetime
from typing import List, Optional, Any, Dict

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import FetchLogModel
from src.db.session import Database


class FetchLogRepository:
    """Repository for fetch log operations."""

    def __init__(self, db: Database):
        """
        Initialize repository with database instance.

        Args:
            db: Database instance
        """
        self.db = db

    async def create_log(
        self,
        source: str,
        status: str,
        records_attempted: int,
        records_succeeded: int,
        records_failed: int,
        duration_seconds: float,
        fetch_params: Optional[dict] = None,
        error_count: int = 0,
        error_summary: Optional[List[Dict[str, Any]]] = None,
    ) -> FetchLogModel:
        """
        Create a new fetch log entry.

        Args:
            source: Source of the fetch operation (e.g., "OpenParliament", "LEGISinfo")
            status: Status of the operation ("success", "partial", "error")
            records_attempted: Number of records attempted to fetch
            records_succeeded: Number of records successfully processed
            records_failed: Number of records that failed
            duration_seconds: Duration of the operation in seconds
            fetch_params: Optional parameters used for the fetch
            error_count: Number of errors encountered
            error_summary: Optional structured summary of errors

        Returns:
            Created FetchLogModel instance
        """
        async with self.db.session() as session:
            log = FetchLogModel(
                source=source,
                status=status,
                records_attempted=records_attempted,
                records_succeeded=records_succeeded,
                records_failed=records_failed,
                duration_seconds=duration_seconds,
                fetch_params=fetch_params,
                error_count=error_count,
                error_summary=error_summary,
            )

            session.add(log)
            await session.commit()
            await session.refresh(log)

            return log

    async def get_logs_since(
        self,
        cutoff_time: datetime,
        source: Optional[str] = None,
    ) -> List[FetchLogModel]:
        """
        Get all logs since a specific datetime.

        Args:
            cutoff_time: Datetime to filter logs from
            source: Optional source filter

        Returns:
            List of FetchLogModel instances
        """
        async with self.db.session() as session:
            query = select(FetchLogModel).where(
                FetchLogModel.created_at >= cutoff_time
            )

            if source:
                query = query.where(FetchLogModel.source == source)

            query = query.order_by(FetchLogModel.created_at.desc())

            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_recent_logs(
        self,
        limit: int = 100,
        source: Optional[str] = None,
    ) -> List[FetchLogModel]:
        """
        Get most recent fetch logs.

        Args:
            limit: Maximum number of logs to return
            source: Optional source filter

        Returns:
            List of FetchLogModel instances
        """
        async with self.db.session() as session:
            query = select(FetchLogModel)

            if source:
                query = query.where(FetchLogModel.source == source)

            query = query.order_by(
                FetchLogModel.created_at.desc()).limit(limit)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_last_successful_bill_window(
        self,
        *,
        source: str = "bill_integration_service",
        parliament: Optional[int] = None,
        session_filter: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return the fetch parameter snapshot from the most recent successful run.

        The method inspects recent log entries, starting from the newest, and returns the
        ``fetch_params`` dict for the first log that matches the optional parliament/session
        filters. ``None`` is returned if no matching log exists.
        """

        async with self.db.session() as session:
            query = (
                select(FetchLogModel)
                .where(
                    FetchLogModel.source == source,
                    FetchLogModel.status == "success",
                )
                .order_by(FetchLogModel.created_at.desc())
                .limit(200)
            )

            result = await session.execute(query)
            logs: List[FetchLogModel] = list(result.scalars().all())

        for log in logs:
            params: Dict[str, Any] = log.fetch_params or {}
            if parliament is not None:
                raw_parliament = params.get("parliament")
                try:
                    stored_parliament = int(raw_parliament)
                except (TypeError, ValueError):
                    stored_parliament = None
                if stored_parliament != parliament:
                    continue

            if session_filter is not None:
                stored_session = params.get("session")
                if stored_session is None:
                    continue
                try:
                    session_value = int(stored_session)
                except (TypeError, ValueError):
                    session_value = None
                if session_value != session_filter:
                    continue

            return params

        return None
