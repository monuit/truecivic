"""
Committee Adapter for OpenParliament API.

Fetches parliamentary committee data including committee info and meetings.
"""
from datetime import datetime
from typing import List, Dict, Any, Optional, cast

import httpx

from src.models.adapter_models import (
    CommitteeData,
    CommitteeMeetingData,
    AdapterResponse,
    AdapterError,
)
from src.adapters.base_adapter import BaseAdapter
from src.adapters.committee_normalizer import (
    parse_committee,
    parse_committee_meeting,
    enrich_committee_meeting_detail,
)
from src.utils.committee_registry import build_committee_identifier


class CommitteeAdapter(BaseAdapter[CommitteeData]):
    """Adapter for fetching committee data from OpenParliament API."""

    def __init__(self, api_base_url: str = "https://api.openparliament.ca"):
        super().__init__(
            source_name="openparliament_committees",
            rate_limit_per_second=1.0,
            max_retries=3,
            timeout_seconds=30,
        )
        self.api_base_url = api_base_url
        self.client = httpx.AsyncClient(
            timeout=self.timeout_seconds,
            headers={
                "User-Agent": "TrueCivic/committee-adapter",
                "Accept": "application/json",
            },
        )

    async def fetch(self, **kwargs: Any):  # type: ignore[override]
        """Generic fetch is not implemented for this legacy adapter."""
        raise NotImplementedError(
            "Use fetch_committees_for_session or fetch_all_committees instead."
        )

    # type: ignore[override]
    def normalize(self, raw_data: Any) -> CommitteeData:
        """Normalization is handled by specialized parser helpers."""
        raise NotImplementedError(
            "CommitteeAdapter uses parse_committee helper for normalization."
        )

    async def close(self) -> None:
        """Release underlying HTTP resources."""
        await self.client.aclose()

    async def fetch_committees_for_session(
        self,
        parliament: int,
        session: int,
        limit: int = 100
    ) -> AdapterResponse[CommitteeData]:
        """
        Fetch all committees for a given parliament session.

        Args:
            parliament: Parliament number (e.g., 44)
            session: Session number (e.g., 1)
            limit: Results per page

        Returns:
            AdapterResponse with committee records for the session
        """
        self._reset_metrics()
        start_time = datetime.utcnow()
        committees: List[CommitteeData] = []
        errors: List[AdapterError] = []

        current_url = f"{self.api_base_url}/committees/"
        current_params: Optional[Dict[str, Any]] = {
            "session": f"{parliament}-{session}",
            "limit": limit,
            "format": "json",
        }
        not_modified = False

        self.logger.info(
            "Fetching committees for Parliament %s, Session %s",
            parliament,
            session,
        )

        try:
            while current_url:
                response = await self._http_get(
                    self.client,
                    current_url,
                    params=current_params,
                    cache_key=self._cache_key(current_url, current_params),
                )

                if response.status_code == httpx.codes.NOT_MODIFIED:
                    not_modified = True
                    self.logger.info(
                        "%s returned 304 Not Modified; ending fetch",
                        current_url,
                    )
                    break

                response.raise_for_status()
                data = response.json()

                for committee_obj in data.get("objects", []):
                    committee = parse_committee(
                        committee_obj,
                        parliament,
                        session,
                        self.api_base_url,
                    )
                    if committee:
                        committees.append(committee)
                    else:
                        errors.append(
                            AdapterError(
                                timestamp=datetime.utcnow(),
                                error_type="ParseError",
                                message="Unable to normalize committee payload",
                                context={
                                    "parliament": parliament,
                                    "session": session,
                                    "payload_slug": committee_obj.get("slug"),
                                },
                                retryable=False,
                            )
                        )

                next_url = data.get("pagination", {}).get("next_url")
                if next_url:
                    current_url = (
                        f"{self.api_base_url}{next_url}"
                        if next_url.startswith("/")
                        else next_url
                    )
                else:
                    current_url = None
                current_params = None

            self.logger.info(
                "Fetched %s committees for %s-%s",
                len(committees),
                parliament,
                session,
            )

            return self._build_success_response(
                data=committees,
                errors=errors,
                start_time=start_time,
                metadata={
                    "not_modified": not_modified,
                    "parliament": parliament,
                    "session": session,
                    "record_count": len(committees),
                },
            )

        except httpx.HTTPError as exc:
            self.logger.error(
                "HTTP error fetching committees for %s-%s: %s",
                parliament,
                session,
                exc,
                exc_info=True,
            )
            return self._build_failure_response(exc, start_time, retryable=True)
        except Exception as exc:
            self.logger.error(
                "Unexpected error fetching committees for %s-%s: %s",
                parliament,
                session,
                exc,
                exc_info=True,
            )
            return self._build_failure_response(exc, start_time, retryable=False)

    async def fetch_committee_detail(
        self,
        committee_slug: str,
        parliament: int,
        session: int,
    ) -> AdapterResponse[CommitteeData]:
        """
        Fetch detailed committee information.

        Args:
            committee_slug: Committee slug/acronym (e.g., "HUMA")
            parliament: Parliament number
            session: Session number

        Returns:
            AdapterResponse containing the committee record, if available
        """
        self._reset_metrics()
        start_time = datetime.utcnow()
        url = f"{self.api_base_url}/committees/{committee_slug}/"
        params = {
            "session": f"{parliament}-{session}",
            "format": "json",
        }
        cache_key = self._cache_key(url, params)

        try:
            response = await self._http_get(
                self.client,
                url,
                params=params,
                cache_key=cache_key,
            )

            if response.status_code == httpx.codes.NOT_MODIFIED:
                return self._build_success_response(
                    data=[],
                    errors=[],
                    start_time=start_time,
                    metadata={
                        "not_modified": True,
                        "committee_slug": committee_slug,
                    },
                )

            response.raise_for_status()
            payload = response.json()
            committee = parse_committee(
                payload,
                parliament,
                session,
                self.api_base_url,
            )

            if committee is None:
                parse_error = AdapterError(
                    timestamp=datetime.utcnow(),
                    error_type="ParseError",
                    message="Unable to normalize committee detail",
                    context={
                        "committee_slug": committee_slug,
                        "parliament": parliament,
                        "session": session,
                    },
                    retryable=False,
                )
                return self._build_success_response(
                    data=[],
                    errors=[parse_error],
                    start_time=start_time,
                    metadata={
                        "not_modified": False,
                        "committee_slug": committee_slug,
                    },
                )

            return self._build_success_response(
                data=[committee],
                errors=[],
                start_time=start_time,
                metadata={
                    "not_modified": False,
                    "committee_slug": committee_slug,
                },
            )

        except httpx.HTTPError as exc:
            self.logger.error(
                "HTTP error fetching committee detail %s: %s",
                committee_slug,
                exc,
                exc_info=True,
            )
            return self._build_failure_response(exc, start_time, retryable=True)
        except Exception as exc:
            self.logger.error(
                "Unexpected error fetching committee detail %s: %s",
                committee_slug,
                exc,
                exc_info=True,
            )
            return self._build_failure_response(exc, start_time, retryable=False)

    async def fetch_committee_activities(
        self,
        committee_slug: str,
        parliament: int,
        session: int,
        limit: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Fetch committee activities (meetings, reports, etc.).

        Args:
            committee_slug: Committee slug/acronym
            parliament: Parliament number
            session: Session number
            limit: Results per page

        Returns:
            List of activity dictionaries
        """
        self._reset_metrics()
        activities: List[Dict[str, Any]] = []
        current_url = f"{self.api_base_url}/committees/{committee_slug}/activities/"
        current_params: Optional[Dict[str, Any]] = {
            "session": f"{parliament}-{session}",
            "limit": limit,
            "format": "json",
        }

        self.logger.info(
            "Fetching activities for committee %s", committee_slug)

        while current_url:
            response = await self._http_get(
                self.client,
                current_url,
                params=current_params,
                cache_key=self._cache_key(current_url, current_params),
            )

            if response.status_code == httpx.codes.NOT_MODIFIED:
                self.logger.info(
                    "%s returned 304 Not Modified; ending activities fetch",
                    current_url,
                )
                break

            response.raise_for_status()
            data = response.json()

            batch = data.get("objects", [])
            if batch:
                activities.extend(batch)

            next_url = data.get("pagination", {}).get("next_url")
            if next_url:
                current_url = (
                    f"{self.api_base_url}{next_url}"
                    if next_url.startswith("/")
                    else next_url
                )
            else:
                current_url = None
            current_params = None

        self.logger.info(
            "Fetched %s activities for committee %s",
            len(activities),
            committee_slug,
        )

        return activities

    async def fetch_committee_meetings(
        self,
        committee_identifier: str,
        parliament: int,
        session: int,
        limit: int = 100,
        include_details: bool = True,
    ) -> AdapterResponse[CommitteeMeetingData]:
        """Fetch and normalize committee meeting payloads."""

        self._reset_metrics()
        start_time = datetime.utcnow()
        meetings: List[CommitteeMeetingData] = []
        errors: List[AdapterError] = []

        try:
            identifier = build_committee_identifier(committee_identifier)
        except ValueError as exc:
            return cast(
                AdapterResponse[CommitteeMeetingData],
                self._build_failure_response(exc, start_time, retryable=False),
            )

        source_slug = identifier.source_slug
        if not source_slug:
            source_slug = identifier.code.lower()

        current_url = f"{self.api_base_url}/committees/meetings/"
        current_params: Optional[Dict[str, Any]] = {
            "format": "json",
            "limit": min(limit, 100),
            "committee": source_slug,
            "parliament": parliament,
            "session": session,
        }
        fetched = 0

        try:
            while current_url and fetched < limit:
                response = await self._http_get(
                    self.client,
                    current_url,
                    params=current_params,
                    cache_key=self._cache_key(current_url, current_params),
                )

                if response.status_code == httpx.codes.NOT_MODIFIED:
                    break

                response.raise_for_status()
                payload = response.json()
                objects = payload.get("objects", [])

                for raw_meeting in objects:
                    if fetched >= limit:
                        break
                    meeting = parse_committee_meeting(
                        raw_meeting,
                        identifier.code,
                        parliament,
                        session,
                        self.api_base_url,
                    )
                    if meeting:
                        if include_details:
                            detail_id = raw_meeting.get("id")
                            if isinstance(detail_id, int):
                                detail = await self._fetch_meeting_detail(detail_id)
                                if isinstance(detail, dict) and detail:
                                    meeting = enrich_committee_meeting_detail(
                                        meeting, detail)
                                elif isinstance(detail, AdapterError):
                                    errors.append(detail)
                        meetings.append(meeting)
                        fetched += 1
                    else:
                        errors.append(
                            AdapterError(
                                timestamp=datetime.utcnow(),
                                error_type="ParseError",
                                message="Unable to normalize committee meeting",
                                context={
                                    "committee": identifier.code,
                                    "meeting_raw": raw_meeting.get("url"),
                                },
                                retryable=False,
                            )
                        )

                next_url = payload.get("pagination", {}).get("next_url")
                if next_url and fetched < limit:
                    current_url = (
                        f"{self.api_base_url}{next_url}"
                        if next_url.startswith("/")
                        else next_url
                    )
                    current_params = None
                else:
                    current_url = None

            metadata = {
                "committee_slug": identifier.internal_slug,
                "committee_code": identifier.code,
                "record_count": len(meetings),
                "parliament": parliament,
                "session": session,
                "details_hydrated": include_details,
            }
            return cast(
                AdapterResponse[CommitteeMeetingData],
                self._build_success_response(
                    data=meetings,
                    errors=errors,
                    start_time=start_time,
                    metadata=metadata,
                ),
            )

        except httpx.HTTPError as exc:
            return cast(
                AdapterResponse[CommitteeMeetingData],
                self._build_failure_response(exc, start_time, retryable=True),
            )
        except Exception as exc:
            return cast(
                AdapterResponse[CommitteeMeetingData],
                self._build_failure_response(exc, start_time, retryable=False),
            )

    async def _fetch_meeting_detail(self, meeting_id: int) -> Any:
        """Fetch a single meeting detail payload."""

        url = f"{self.api_base_url}/committees/meetings/{meeting_id}/"
        detail_response = await self._http_get(
            self.client,
            url,
            params={"format": "json"},
            cache_key=self._cache_key(url, {"format": "json"}),
        )

        if detail_response.status_code == httpx.codes.NOT_MODIFIED:
            return {}

        try:
            detail_response.raise_for_status()
            return detail_response.json()
        except httpx.HTTPError as exc:  # pragma: no cover - defensive
            return AdapterError(
                timestamp=datetime.utcnow(),
                error_type="HTTPError",
                message=str(exc),
                context={"meeting_id": meeting_id},
                retryable=True,
            )
        except Exception as exc:  # pragma: no cover - defensive
            return AdapterError(
                timestamp=datetime.utcnow(),
                error_type=type(exc).__name__,
                message=str(exc),
                context={"meeting_id": meeting_id},
                retryable=False,
            )

    async def fetch_all_committees(self, limit: int = 100) -> AdapterResponse[CommitteeData]:
        """
        Fetch all committees across all sessions.

        Args:
            limit: Results per page

        Returns:
            AdapterResponse aggregating all committee records
        """
        self._reset_metrics()
        start_time = datetime.utcnow()
        committees: List[CommitteeData] = []
        errors: List[AdapterError] = []

        current_url = f"{self.api_base_url}/committees/"
        current_params: Optional[Dict[str, Any]] = {
            "limit": limit,
            "format": "json",
        }
        not_modified = False

        self.logger.info("Fetching all committees across sessions")

        try:
            while current_url:
                response = await self._http_get(
                    self.client,
                    current_url,
                    params=current_params,
                    cache_key=self._cache_key(current_url, current_params),
                )

                if response.status_code == httpx.codes.NOT_MODIFIED:
                    not_modified = True
                    self.logger.info(
                        "%s returned 304 Not Modified; ending fetch",
                        current_url,
                    )
                    break

                response.raise_for_status()
                data = response.json()

                for committee_obj in data.get("objects", []):
                    try:
                        session_info = committee_obj.get("sessions", [])
                        parliament_value: int = 44
                        session_value: int = 1
                        if session_info:
                            latest_session = (
                                session_info[0]
                                if isinstance(session_info, list)
                                else session_info
                            )
                            if isinstance(latest_session, dict):
                                parliament_value = int(latest_session.get(
                                    "parliamentnum") or parliament_value)
                                session_value = int(latest_session.get(
                                    "sessnum") or session_value)
                            else:
                                parts = str(latest_session).split("-")
                                if parts and parts[0].isdigit():
                                    parliament_value = int(parts[0])
                                if len(parts) > 1 and parts[1].isdigit():
                                    session_value = int(parts[1])

                        committee = parse_committee(
                            committee_obj,
                            parliament_value,
                            session_value,
                            self.api_base_url,
                        )
                        if committee:
                            committees.append(committee)
                        else:
                            errors.append(
                                AdapterError(
                                    timestamp=datetime.utcnow(),
                                    error_type="ParseError",
                                    message="Unable to normalize committee payload",
                                    context={
                                        "detected_parliament": parliament_value,
                                        "detected_session": session_value,
                                    },
                                    retryable=False,
                                )
                            )
                    except Exception as exc:
                        self.logger.error("Error parsing committee: %s", exc)
                        errors.append(
                            AdapterError(
                                timestamp=datetime.utcnow(),
                                error_type=type(exc).__name__,
                                message=str(exc),
                                context={"payload": committee_obj.get("slug")},
                                retryable=False,
                            )
                        )

                next_url = data.get("pagination", {}).get("next_url")
                if next_url:
                    current_url = (
                        f"{self.api_base_url}{next_url}"
                        if next_url.startswith("/")
                        else next_url
                    )
                else:
                    current_url = None
                current_params = None

            self.logger.info(
                "Fetched %s committees across all sessions",
                len(committees),
            )

            return self._build_success_response(
                data=committees,
                errors=errors,
                start_time=start_time,
                metadata={
                    "not_modified": not_modified,
                    "record_count": len(committees),
                    "limit": limit,
                },
            )

        except httpx.HTTPError as exc:
            self.logger.error(
                "HTTP error fetching all committees: %s", exc, exc_info=True)
            return self._build_failure_response(exc, start_time, retryable=True)
        except Exception as exc:
            self.logger.error(
                "Unexpected error fetching all committees: %s", exc, exc_info=True
            )
            return self._build_failure_response(exc, start_time, retryable=False)
