"""
OpenParliament API adapter for fetching bills.

Pulls legislative bills from OpenParliament API (api.openparliament.ca).
Supports filtering by parliament/session and sorting to get latest bills first.

Responsibility: Fetch and normalize bills from OpenParliament JSON API
"""

from datetime import datetime
from typing import Optional, Dict, Any
import httpx

from .base_adapter import BaseAdapter
from ..models.bill import Bill
from ..models.adapter_models import AdapterResponse, AdapterError


class OpenParliamentBillsAdapter(BaseAdapter[Bill]):
    """
    Adapter for fetching bills from OpenParliament API.

    Key features:
    - Fetches bills in reverse chronological order (latest first)
    - Supports pagination for large result sets
    - Extracts legisinfo_id for enrichment linking
    - Handles bilingual content (EN/FR)
    - Rate limited to 2 requests/second

    Example:
        adapter = OpenParliamentBillsAdapter()
        response = await adapter.fetch(parliament=44, session=1, limit=100)
    """

    BASE_URL = "https://api.openparliament.ca"

    def __init__(self):
        """Initialize OpenParliament bills adapter"""
        super().__init__(
            source_name="openparliament_bills",
            rate_limit_per_second=2.0,  # 2 req/sec = gentle
            max_retries=3,
            timeout_seconds=30
        )

        # Initialize HTTP client
        self.client = httpx.AsyncClient(
            timeout=self.timeout_seconds,
            headers={
                "User-Agent": "ParliamentExplorer/1.0 (production)",
                "Accept": "application/json"
            },
            follow_redirects=True
        )

    async def fetch(
        self,
        parliament: Optional[int] = None,
        session: Optional[int] = None,
        limit: int = 100,
        introduced_after: Optional[datetime] = None,
        introduced_before: Optional[datetime] = None,
        **kwargs: Any
    ) -> AdapterResponse[Bill]:
        """
        Fetch bills from OpenParliament API.

        Bills are returned in REVERSE CHRONOLOGICAL ORDER (latest first)
        using the -introduced date sort parameter.

        Args:
            parliament: Filter by parliament number (e.g., 44)
            session: Filter by session number (e.g., 1)
            limit: Maximum records to fetch (pagination handled automatically)
            **kwargs: Additional parameters (ignored)

        Returns:
            AdapterResponse containing list of Bill objects
        """
        self._reset_metrics()
        start_time = datetime.utcnow()
        bills: list[Bill] = []
        errors: list[AdapterError] = []

        self.logger.info(
            f"Fetching bills: parliament={parliament}, session={session}, limit={limit}"
        )

        try:
            # Build initial URL with filters
            url = f"{self.BASE_URL}/bills/"
            params: Dict[str, Any] = {
                "format": "json",
                "limit": min(limit, 100),  # API max per page
                # CRITICAL: Latest bills first (DESC)
                "order_by": "-introduced"
            }

            if parliament:
                # Note: OpenParliament uses session filtering differently; fetch all and filter locally.
                self.logger.debug(
                    "Filtering for parliament %s, session %s",
                    parliament,
                    session,
                )

            if introduced_after:
                params["introduced__gte"] = introduced_after.date().isoformat()
            if introduced_before:
                params["introduced__lte"] = introduced_before.date().isoformat()

            records_fetched = 0
            not_modified = False

            # Paginate through results
            current_url = url
            current_params: Optional[Dict[str, Any]] = params
            while current_url and records_fetched < limit:
                self.logger.debug("GET %s", current_url)

                response = await self._http_get(
                    self.client,
                    current_url,
                    params=current_params,
                    cache_key=self._cache_key(current_url, current_params),
                )

                if response.status_code == httpx.codes.NOT_MODIFIED:
                    not_modified = True
                    self.logger.info(
                        "%s responded 304 Not Modified; stopping pagination",
                        current_url,
                    )
                    break

                response.raise_for_status()

                data = response.json()

                # Extract bills from response
                raw_bills = data.get("objects", [])

                for raw_bill in raw_bills:
                    try:
                        # Normalize each bill
                        bill = self.normalize(raw_bill)

                        # Apply parliament/session filter if specified
                        if parliament and bill.parliament != parliament:
                            continue
                        if session and bill.session != session:
                            continue
                        if introduced_after and bill.introduced_date and bill.introduced_date < introduced_after:
                            continue
                        if introduced_before and bill.introduced_date and bill.introduced_date > introduced_before:
                            continue
                        if introduced_after and bill.introduced_date is None:
                            continue

                        bills.append(bill)
                        records_fetched += 1

                        # Stop if we've hit limit
                        if records_fetched >= limit:
                            break

                    except Exception as e:
                        # Log normalization error but continue
                        self.logger.warning(
                            f"Failed to normalize bill: {e}",
                            exc_info=True
                        )
                        errors.append(AdapterError(
                            timestamp=datetime.utcnow(),
                            error_type=type(e).__name__,
                            message=str(e),
                            context={"bill_url": raw_bill.get(
                                "url", "unknown")},
                            retryable=False
                        ))

                # Check for next page
                pagination = data.get("pagination", {})
                next_url = pagination.get("next_url")

                if next_url:
                    # Handle relative URLs
                    current_url = (
                        f"{self.BASE_URL}{next_url}"
                        if next_url.startswith("/")
                        else next_url
                    )
                else:
                    current_url = None

                current_params = None  # Next URL has params embedded

                self.logger.debug(
                    f"Fetched {len(raw_bills)} bills, "
                    f"total so far: {records_fetched}"
                )

            self.logger.info(
                f"Successfully fetched {len(bills)} bills, "
                f"{len(errors)} errors"
            )

            # Build success response
            return self._build_success_response(
                data=bills,
                errors=errors,
                start_time=start_time,
                cache_ttl_seconds=6 * 3600,  # Cache for 6 hours
                metadata={"not_modified": not_modified},
            )

        except httpx.HTTPError as e:
            # Network/HTTP error - entire operation failed
            self.logger.error(f"HTTP error fetching bills: {e}", exc_info=True)
            return self._build_failure_response(
                error=e,
                start_time=start_time,
                retryable=True
            )

        except Exception as e:
            # Unexpected error
            self.logger.error(
                f"Unexpected error fetching bills: {e}", exc_info=True)
            return self._build_failure_response(
                error=e,
                start_time=start_time,
                retryable=False
            )

    def normalize(self, raw_data: Dict[str, Any]) -> Bill:
        """
        Normalize OpenParliament bill JSON to Bill model.

        Args:
            raw_data: Raw bill dict from OpenParliament API

        Returns:
            Normalized Bill instance

        Raises:
            ValueError: If required fields are missing
        """
        # Extract parliament/session from session field
        # Format: "44-1" (parliament-session)
        session_str = raw_data.get("session")
        if not session_str:
            raise ValueError("Bill missing session field")

        # Parse session string
        parts = session_str.split("-")

        if len(parts) != 2:
            raise ValueError(f"Invalid session format: {session_str}")

        parliament = int(parts[0])
        session = int(parts[1])

        # Extract bill number
        number = raw_data.get("number")
        if not number:
            raise ValueError("Bill missing number field")

        # Extract titles
        name = raw_data.get("name", {})
        title_en = name.get("en", "")
        title_fr = name.get("fr")

        short_title = raw_data.get("short_title", {})
        short_title_en = short_title.get("en") if short_title else None
        short_title_fr = short_title.get("fr") if short_title else None

        # Extract sponsor ID
        sponsor_url = raw_data.get("sponsor_politician_url")
        sponsor_id = self._extract_id_from_url(
            sponsor_url) if sponsor_url else None

        # Extract legisinfo_id (CRITICAL for enrichment)
        legisinfo_id = raw_data.get("legisinfo_id")

        # Extract dates
        introduced_date = self._parse_date(raw_data.get("introduced"))

        # Extract law status
        law_status = raw_data.get("law")

        return Bill(
            jurisdiction="ca-federal",
            parliament=parliament,
            session=session,
            number=number,
            title_en=title_en,
            title_fr=title_fr,
            short_title_en=short_title_en,
            short_title_fr=short_title_fr,
            sponsor_politician_id=sponsor_id,
            introduced_date=introduced_date,
            law_status=law_status,
            legisinfo_id=legisinfo_id,
            source_openparliament=True,
            last_fetched_at=datetime.utcnow()
        )

    def _extract_id_from_url(self, url: str) -> Optional[int]:
        """
        Extract numeric ID from OpenParliament URL.

        Example: "/politicians/123/" -> 123
        """
        try:
            parts = url.strip("/").split("/")
            return int(parts[-1])
        except (ValueError, IndexError):
            return None

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse ISO date string to datetime.

        Example: "2023-01-15" -> datetime(2023, 1, 15)
        """
        if not date_str:
            return None
        try:
            # Handle both date and datetime formats
            if "T" in date_str:
                # ISO datetime format
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                # Date only format
                return datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, AttributeError):
            return None

    async def close(self):
        """Close HTTP client connection"""
        await self.client.aclose()
