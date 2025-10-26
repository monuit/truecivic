"""Committee payload normalization helpers.

Provides utility functions for converting OpenParliament committee
responses into the internal ``CommitteeData`` representation.

Single responsibility: shared normalization logic used by
``CommitteeAdapter`` and related consumers.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, List
from datetime import datetime

from src.models.adapter_models import CommitteeData, CommitteeMeetingData
from src.utils.committee_registry import build_committee_identifier, resolve_source_slug

logger = logging.getLogger(__name__)


def parse_committee(
    data: Dict[str, Any],
    parliament: int,
    session: int,
    api_base_url: str,
) -> Optional[CommitteeData]:
    """Convert a committee payload into ``CommitteeData``.

    Args:
        data: Raw committee payload from OpenParliament.
        parliament: Target parliament number.
        session: Target session number.
        api_base_url: Base URL for resolving relative source URLs.

    Returns:
        ``CommitteeData`` instance when normalization succeeds, otherwise ``None``.
    """
    try:
        slug = data.get("slug")
        if not slug:
            url_hint = data.get("url")
            if isinstance(url_hint, str) and url_hint:
                slug = url_hint.strip("/").split("/")[-1]
        if not slug:
            return None

        target_session_key = f"{parliament}-{session}"
        sessions_payload = data.get("sessions") or []
        matched_session: Optional[Dict[str, Any]] = None
        if isinstance(sessions_payload, list):
            for session_entry in sessions_payload:
                session_value = session_entry.get(
                    "session") or session_entry.get("sessnum")
                if session_value is None:
                    continue
                session_text = str(session_value).strip()
                if session_text == target_session_key:
                    matched_session = session_entry
                    break
            if matched_session is None and sessions_payload:
                matched_session = sessions_payload[0]

        acronym_payload = data.get("acronym") or data.get("acronym_en")
        acronym_en: Optional[str]
        acronym_fr: Optional[str]
        if isinstance(acronym_payload, dict):
            acronym_en = acronym_payload.get("en") or acronym_payload.get("fr")
            acronym_fr = acronym_payload.get("fr") or acronym_payload.get("en")
        elif isinstance(acronym_payload, str):
            acronym_en = acronym_payload
            acronym_fr = None
        else:
            acronym_en = None
            acronym_fr = None

        if matched_session and not acronym_en:
            session_acronym = matched_session.get("acronym")
            if isinstance(session_acronym, str) and session_acronym:
                acronym_en = session_acronym
        if not acronym_fr and matched_session:
            session_acronym = matched_session.get("acronym")
            if isinstance(session_acronym, str) and session_acronym:
                acronym_fr = session_acronym

        identifier_seed = acronym_en or slug
        identifier = build_committee_identifier(identifier_seed)
        internal_slug = identifier.internal_slug
        source_slug = resolve_source_slug(slug) or identifier.source_slug

        acronym_en = (acronym_en or identifier.code).upper()
        if not acronym_fr:
            acronym_fr = acronym_en

        name_en_raw = data.get("name_en") or data.get("name")
        name_fr_raw = data.get("name_fr") or data.get("name")

        if isinstance(name_en_raw, dict):
            name_en = name_en_raw.get("en") or name_en_raw.get("fr")
        else:
            name_en = name_en_raw

        if isinstance(name_fr_raw, dict):
            name_fr = name_fr_raw.get("fr") or name_fr_raw.get("en")
        else:
            name_fr = name_fr_raw

        short_name_en_raw = data.get("short_name_en") or data.get("short_name")
        short_name_fr_raw = data.get("short_name_fr") or data.get("short_name")

        if isinstance(short_name_en_raw, dict):
            short_name_en = short_name_en_raw.get(
                "en") or short_name_en_raw.get("fr")
        else:
            short_name_en = short_name_en_raw

        if isinstance(short_name_fr_raw, dict):
            short_name_fr = short_name_fr_raw.get(
                "fr") or short_name_fr_raw.get("en")
        else:
            short_name_fr = short_name_fr_raw

        parent_committee = data.get("parent")
        parent_slug: Optional[str] = None
        if parent_committee:
            if isinstance(parent_committee, dict):
                parent_slug = parent_committee.get(
                    "slug") or parent_committee.get("code")
            elif isinstance(parent_committee, str):
                parent_slug = parent_committee
        else:
            parent_url = data.get("parent_url")
            if isinstance(parent_url, str) and parent_url:
                parent_slug = parent_url.strip("/").split("/")[-1]

        if parent_slug:
            try:
                parent_identifier = build_committee_identifier(parent_slug)
                parent_slug = parent_identifier.internal_slug
            except ValueError:
                parent_slug = parent_slug

        chamber = "House"
        normalized_name_en = (name_en or "") if isinstance(
            name_en, str) else str(name_en or "")

        if data.get("joint"):
            chamber = "Joint"
        elif "senate" in normalized_name_en.lower():
            chamber = "Senate"

        source_url: Optional[str] = None
        if matched_session:
            source_url = matched_session.get("source_url")
        if not source_url:
            raw_url = data.get("source_url") or data.get("url")
            if isinstance(raw_url, str) and raw_url:
                if raw_url.startswith("http"):
                    source_url = raw_url
                elif raw_url.startswith("/"):
                    source_url = f"{api_base_url}{raw_url}"
        if not source_url:
            source_url = (
                "https://www.ourcommons.ca/Committees/en/"
                f"{identifier.code}?parl={parliament}&session={session}"
            )

        natural_id = f"ca-federal-{parliament}-{session}-committee-{identifier.code}"

        return CommitteeData(
            committee_id=natural_id,
            parliament=parliament,
            session=session,
            committee_slug=internal_slug,
            source_slug=source_slug,
            acronym_en=acronym_en,
            acronym_fr=acronym_fr,
            name_en=name_en,
            name_fr=name_fr,
            short_name_en=short_name_en,
            short_name_fr=short_name_fr,
            chamber=chamber,
            parent_committee=parent_slug,
            source_url=source_url,
        )

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Error parsing committee data: %s", exc)
        return None


def parse_committee_meeting(
    data: Dict[str, Any],
    identifier_seed: str,
    default_parliament: int,
    default_session: int,
    api_base_url: str,
) -> Optional[CommitteeMeetingData]:
    """Normalize an OpenParliament meeting payload into ``CommitteeMeetingData``."""

    try:
        identifier = build_committee_identifier(identifier_seed)
    except ValueError as exc:
        logger.warning(
            "Unable to resolve committee identifier for meeting: %s", exc)
        return None

    parliament = _resolve_parliament_value(
        data.get("parliament"), default_parliament)
    session = _resolve_session_value(data.get("session"), default_session)

    meeting_number = _safe_int(data.get("number"))
    meeting_date = _parse_datetime(data.get("date"))

    title_payload = data.get("title")
    title_en: Optional[str]
    title_fr: Optional[str]
    if isinstance(title_payload, dict):
        title_en = title_payload.get("en") or title_payload.get("fr")
        title_fr = title_payload.get("fr") or title_payload.get("en")
    else:
        title_en = title_payload
        title_fr = None

    meeting_type = data.get("meeting_type") or data.get("type")
    room = data.get("room")
    time_of_day = data.get("start_time") or data.get("time")

    source_url = _resolve_meeting_url(api_base_url, data.get("url"))

    return CommitteeMeetingData(
        committee_slug=identifier.internal_slug,
        committee_code=identifier.code,
        meeting_number=meeting_number,
        parliament=parliament,
        session=session,
        meeting_date=meeting_date,
        title_en=title_en,
        title_fr=title_fr,
        meeting_type=meeting_type,
        room=room,
        time_of_day=time_of_day,
        source_url=source_url,
    )


def enrich_committee_meeting_detail(
    meeting: CommitteeMeetingData,
    detail_payload: Dict[str, Any],
) -> CommitteeMeetingData:
    """Attach witness and document metadata to a meeting record."""

    witnesses: List[Dict[str, Any]] = []
    for entry in detail_payload.get("evidence") or []:
        witness = entry.get("witness") or {}
        if witness:
            witnesses.append(
                {
                    "name": witness.get("name"),
                    "organization": witness.get("organization"),
                    "title": witness.get("title"),
                }
            )

    documents: List[Dict[str, Any]] = []
    for doc in detail_payload.get("documents") or []:
        documents.append(
            {
                "title": doc.get("title"),
                "url": doc.get("url"),
                "doc_type": doc.get("doctype") or doc.get("document_type"),
            }
        )

    updated = CommitteeMeetingData(
        committee_slug=meeting.committee_slug,
        committee_code=meeting.committee_code,
        meeting_number=meeting.meeting_number,
        parliament=_resolve_parliament_value(
            detail_payload.get("parliament"), meeting.parliament
        ),
        session=_resolve_session_value(
            detail_payload.get("session"), meeting.session
        ),
        meeting_date=_parse_datetime(
            detail_payload.get("date")) or meeting.meeting_date,
        title_en=meeting.title_en,
        title_fr=meeting.title_fr,
        meeting_type=detail_payload.get(
            "meeting_type") or meeting.meeting_type,
        room=detail_payload.get("room") or meeting.room,
        time_of_day=detail_payload.get("start_time") or meeting.time_of_day,
        source_url=meeting.source_url,
        witnesses=witnesses or None,
        documents=documents or None,
    )
    return updated


def _resolve_parliament_value(value: Any, fallback: int) -> int:
    if value is None:
        return fallback
    if isinstance(value, str) and "-" in value:
        value = value.split("-", 1)[0]
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _resolve_session_value(value: Any, fallback: int) -> int:
    if value is None:
        return fallback
    if isinstance(value, str) and "-" in value:
        value = value.split("-", 1)[-1]
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            # Accept both date-only and datetime strings
            if "T" in text:
                return datetime.fromisoformat(text.replace("Z", "+00:00"))
            return datetime.fromisoformat(text)
        except ValueError:
            try:
                return datetime.fromisoformat(f"{text}T00:00:00")
            except ValueError:
                logger.debug("Unable to parse meeting datetime '%s'", text)
                return None
    return None


def _resolve_meeting_url(base_url: str, path: Optional[str]) -> Optional[str]:
    if not path or not isinstance(path, str):
        return None
    if path.startswith("http"):
        return path
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
