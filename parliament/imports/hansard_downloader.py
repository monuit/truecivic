"""Helpers for downloading and storing House of Commons Hansard XML feeds."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Optional

from django.db import transaction

from lxml import etree

from parliament.core.models import Session
from parliament.hansards.models import Document
from .http_retry import fetch_with_backoff, HttpRequestError

logger = logging.getLogger(__name__)

HANSARD_URL_TEMPLATE = (
    "https://www.ourcommons.ca/Content/House/{parliamentnum}{sessnum}/Debates/"
    "{sitting:03d}/HAN{sitting:03d}-{lang}.XML"
)


class NoDocumentFound(Exception):
    """Raised when a Hansard XML resource is missing."""


@dataclass(frozen=True)
class DebateSource:
    """Represents XML sources for a Hansard debate."""

    number: str
    english_xml_url: str
    french_xml_url: str
    source_id: Optional[int] = None
    allow_missing_paragraph_ids: bool = True


def build_numeric_debate_source(session: Session, sitting_number: int, *, allow_missing_paragraph_ids: bool = True) -> DebateSource:
    """Create a ``DebateSource`` for a numeric sitting."""
    english_url = HANSARD_URL_TEMPLATE.format(
        parliamentnum=session.parliamentnum,
        sessnum=session.sessnum,
        sitting=sitting_number,
        lang="E",
    )
    french_url = HANSARD_URL_TEMPLATE.format(
        parliamentnum=session.parliamentnum,
        sessnum=session.sessnum,
        sitting=sitting_number,
        lang="F",
    )
    return DebateSource(
        number=str(sitting_number),
        english_xml_url=english_url,
        french_xml_url=french_url,
        allow_missing_paragraph_ids=allow_missing_paragraph_ids,
    )


def download_debate(session: Session, source: DebateSource):
    """Fetch Hansard XML for ``source`` and persist a :class:`Document`."""
    try:
        response_en = fetch_with_backoff(source.english_xml_url, allowed_status=(200, 404))
    except HttpRequestError as exc:
        logger.error("Error fetching debate XML: %s", exc)
        raise NoDocumentFound from exc
    if response_en.status_code == 404:
        raise NoDocumentFound
    xml_en = response_en.content.replace(b"\r\n", b"\n")

    try:
        response_fr = fetch_with_backoff(source.french_xml_url)
    except HttpRequestError as exc:
        logger.error("Error fetching French debate XML: %s", exc)
        raise NoDocumentFound from exc
    xml_fr = response_fr.content.replace(b"\r\n", b"\n")

    doc_en = etree.fromstring(xml_en)
    doc_fr = etree.fromstring(xml_fr)

    source_id_attr = doc_en.get("id")
    source_id = source.source_id
    if source_id_attr:
        try:
            attr_value = int(source_id_attr)
        except ValueError as exc:
            raise ValueError(f"Invalid source id attribute: {source_id_attr}") from exc
        if source_id is not None and source_id != attr_value:
            logger.warning("Source id mismatch for %s (expected %s)", source.number, source_id)
        source_id = attr_value
    if source_id is None:
        raise ValueError("Debate XML missing source id")

    if Document.objects.filter(source_id=source_id).exists():
        raise RuntimeError(
            "Document at source_id %s already exists" % source_id
        )

    if int(doc_fr.get("id", source_id)) != source_id:
        raise ValueError("English/French XML source id mismatch")

    if (
        not source.allow_missing_paragraph_ids
        and not _test_has_paragraph_ids(doc_en)
        and not _test_has_paragraph_ids(doc_fr)
    ):
        logger.warning("Missing paragraph IDs, cancelling import for %s", source.number)
        return None

    with transaction.atomic():
        document = Document.objects.create(
            document_type=Document.DEBATE,
            session=session,
            source_id=source_id,
            number=source.number,
        )
        document.save_xml(source.english_xml_url, xml_en, xml_fr)
        logger.info("Saved sitting %s", document.number)
    return document


def _test_has_paragraph_ids(elem):
    """Do all, or almost all, of the paragraphs in this document have IDs?"""
    paratext = elem.xpath("//ParaText")
    paratext_with_id = [pt for pt in paratext if pt.get("id")]
    if not paratext:
        return False
    return (len(paratext_with_id) / float(len(paratext))) > 0.95
