"""Import Hansard listings from the Publications Search feed."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable, Optional
from urllib.parse import urljoin

import requests
from lxml import html

from parliament.core.models import Session
from parliament.hansards.models import Document

from .hansard_downloader import DebateSource
from .http_retry import HttpRequestError, fetch_with_backoff


logger = logging.getLogger(__name__)


# MARK: Data structures


@dataclass(frozen=True)
class PublicationSearchResult:
    """Compact representation of a PublicationSearch record for a Hansard sitting."""

    publication_id: int
    parliament: int
    session: int
    issue: str
    issue_code: Optional[str]
    english_html_url: str
    french_html_url: str
    english_pdf_url: Optional[str]
    french_pdf_url: Optional[str]
    publication_date: str


# MARK: Client


_DOCUMENT_ID_RE = re.compile(r"/(\d+)(?:[#/?]|$)")
_PDF_ISSUE_RE = re.compile(r"HAN(?P<issue>[^/-]+)-[EF]\.PDF", re.IGNORECASE)


class PublicationSearchClient:
    """HTTP client capable of paging through PublicationSearch results."""

    def __init__(
        self,
        *,
        base_url: str = "https://www.ourcommons.ca/PublicationSearch/en/",
        session: requests.Session | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self._session = session or requests.Session()
        self._headers = {"User-Agent": user_agent} if user_agent else None

    def search_debates(
        self,
        *,
        parliament: int,
        session: int,
        page_size: int = 100,
        max_pages: int | None = None,
    ) -> Iterable[PublicationSearchResult]:
        """Yield debate listings for the requested parliament/session."""

        if page_size not in {15, 30, 60, 100}:
            raise ValueError("page_size must be one of 15, 30, 60, 100")

        params_base = {
            "PubType": 37,
            "ParlSes": f"{parliament}-{session}",
            "targetLang": "",
            "RPP": page_size,
        }

        page = 1
        seen_ids: set[int] = set()
        while True:
            if max_pages is not None and page > max_pages:
                break
            params = dict(params_base, Page=page)
            try:
                response = fetch_with_backoff(
                    self.base_url,
                    params=params,
                    headers=self._headers,
                    session=self._session,
                )
            except HttpRequestError:
                logger.exception("PublicationSearch request failed", extra={"page": page})
                raise

            page_results = self._parse_page(
                response.content,
                parliament=parliament,
                session=session,
            )
            if not page_results:
                break

            yielded = False
            for result in page_results:
                if result.publication_id in seen_ids:
                    continue
                seen_ids.add(result.publication_id)
                yielded = True
                yield result

            if not yielded:
                break
            page += 1

    def _parse_page(
        self,
        content: bytes,
        *,
        parliament: int,
        session: int,
    ) -> list[PublicationSearchResult]:
        try:
            document = html.fromstring(content)
        except (html.ParserError, ValueError) as exc:  # pragma: no cover
            logger.warning("Failed to parse PublicationSearch HTML", exc_info=exc)
            return []

        publications = document.xpath(
            (
                "//div[@id='Publications']/div["
                "contains(concat(' ', normalize-space(@class), ' '), ' Publication ')]"
            )
        )
        results: list[PublicationSearchResult] = []
        for publication in publications:
            result = self._parse_publication(publication, parliament, session)
            if result is None:
                continue
            results.append(result)
        return results

    def _parse_publication(
        self,
        node,
        parliament: int,
        session: int,
    ) -> Optional[PublicationSearchResult]:
        title_nodes = node.xpath(
            ".//div[contains(@class,'PublicationTitle')]/a"
        )
        if not title_nodes:
            logger.debug("Skipping publication without title link")
            return None
        title_node = title_nodes[0]
        issue_title = title_node.text_content().strip()

        document_href = title_node.get("href", "").strip()
        publication_id = self._extract_publication_id(document_href)
        if publication_id is None:
            logger.warning("Unable to determine publication id", extra={"href": document_href})
            return None

        english_html = urljoin(self.base_url, document_href)
        english_html = english_html.split("#", 1)[0]
        french_html = english_html.replace("/en/", "/fr/", 1)

        publication_date = self._extract_date(node)

        english_pdf, french_pdf, issue_code = self._extract_pdf_links(node)

        return PublicationSearchResult(
            publication_id=publication_id,
            parliament=parliament,
            session=session,
            issue=issue_title,
            issue_code=issue_code,
            english_html_url=english_html,
            french_html_url=french_html,
            english_pdf_url=english_pdf,
            french_pdf_url=french_pdf,
            publication_date=publication_date,
        )

    @staticmethod
    def _extract_publication_id(href: str) -> Optional[int]:
        match = _DOCUMENT_ID_RE.search(href)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:  # pragma: no cover - safety net
            return None

    @staticmethod
    def _extract_date(node) -> str:
        date_nodes = node.xpath(
            ".//div[contains(@class,'PublicationTitle')]/div[contains(@class,'PublicationDate')]"
        )
        if not date_nodes:
            return ""
        return date_nodes[0].text_content().strip()

    def _extract_pdf_links(self, node) -> tuple[Optional[str], Optional[str], Optional[str]]:
        pdf_nodes = node.xpath(
            (
                ".//div[contains(@class,'PublicationHeaderButtons')]/"
                "a[contains(translate(@href, 'pdf', 'PDF'), '.PDF')]"
            )
        )
        if not pdf_nodes:
            return None, None, None

        href = pdf_nodes[0].get("href", "").strip()
        if not href:
            return None, None, None

        english_pdf = urljoin(self.base_url, href).split("#", 1)[0]
        if "-F.PDF" in english_pdf and "-E.PDF" not in english_pdf:
            english_pdf = english_pdf.replace("-F.PDF", "-E.PDF")
        issue_code = self._derive_issue_code(english_pdf)

        french_pdf = None
        if "-E.PDF" in english_pdf:
            french_pdf = english_pdf.replace("-E.PDF", "-F.PDF")

        return english_pdf, french_pdf, issue_code

    @staticmethod
    def _derive_issue_code(pdf_url: str | None) -> Optional[str]:
        if not pdf_url:
            return None
        match = _PDF_ISSUE_RE.search(pdf_url)
        if not match:
            return None
        return match.group("issue")


# MARK: Provider


def _issue_label(issue: str, issue_code: Optional[str]) -> str:
    if issue_code:
        trimmed = issue_code.lstrip("0")
        return trimmed or issue_code
    prefix = "Hansard - "
    if issue.startswith(prefix):
        return issue[len(prefix):].strip() or issue
    return issue.strip()


def _build_xml_urls(result: PublicationSearchResult) -> tuple[Optional[str], Optional[str]]:
    pdf_url = result.english_pdf_url
    if not pdf_url:
        return None, None

    english_xml = pdf_url.replace(".PDF", ".XML") if pdf_url else None
    french_xml = None
    if english_xml and "-E.XML" in english_xml:
        french_xml = english_xml.replace("-E.XML", "-F.XML")
    elif result.french_pdf_url:
        french_xml = result.french_pdf_url.replace(".PDF", ".XML")

    return english_xml, french_xml


class PublicationSearchDebateProvider:
    """Generate :class:`~parliament.imports.hansard_downloader.DebateSource` entries from PublicationSearch."""

    def __init__(self, client: PublicationSearchClient) -> None:
        self._client = client

    def iter_new_debates(self, session: Session) -> Iterable[DebateSource]:
        existing_source_ids = set(
            Document.objects.filter(
                session=session,
                document_type=Document.DEBATE,
            ).values_list("source_id", flat=True)
        )

        for result in self._client.search_debates(
            parliament=session.parliamentnum,
            session=session.sessnum,
        ):
            if result.publication_id in existing_source_ids:
                continue

            english_xml, french_xml = _build_xml_urls(result)
            if not english_xml or not french_xml:
                logger.warning(
                    "Skipping publication without XML URLs",
                    extra={"publication_id": result.publication_id},
                )
                continue

            yield DebateSource(
                number=_issue_label(result.issue, result.issue_code),
                english_xml_url=english_xml,
                french_xml_url=french_xml,
                source_id=result.publication_id,
            )
