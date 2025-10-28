from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Iterable, List
from unittest.mock import Mock, patch

from django.test import TestCase

from parliament.core.models import Session
from parliament.hansards.models import Document
from parliament.imports.publicationsearch_provider import (
    PublicationSearchClient,
    PublicationSearchDebateProvider,
    PublicationSearchResult,
)


class _HttpResponseMock:
    def __init__(self, payload: str) -> None:
        self.content = payload.encode("utf-8")


class PublicationSearchClientTests(TestCase):
    def setUp(self) -> None:
        self.client = PublicationSearchClient()

    def test_search_debates_paginates_and_deduplicates(self) -> None:
        page_one = """
        <div id="Publications">
            <div class="Publication">
                <div class="PublicationTitle">
                    <a href="/DocumentViewer/en/house-debate/123">Hansard - 001</a>
                    <div class="PublicationDate">2024-01-01</div>
                </div>
                <div class="PublicationHeaderButtons">
                    <a href="/Content/House/441/Debates/001/HAN001-E.PDF">PDF</a>
                </div>
            </div>
            <div class="Publication">
                <div class="PublicationTitle">
                    <a href="/DocumentViewer/en/house-debate/456">Hansard - Special</a>
                    <div class="PublicationDate">2024-01-02</div>
                </div>
                <div class="PublicationHeaderButtons">
                    <a href="/Content/House/441/Debates/002/HANSPC-E.PDF">PDF</a>
                </div>
            </div>
        </div>
        """
        page_two = """
        <div id="Publications">
            <div class="Publication">
                <div class="PublicationTitle">
                    <a href="/DocumentViewer/en/house-debate/123">Duplicate Hansard</a>
                    <div class="PublicationDate">2024-01-03</div>
                </div>
                <div class="PublicationHeaderButtons">
                    <a href="/Content/House/441/Debates/003/HAN003-E.PDF">PDF</a>
                </div>
            </div>
            <div class="Publication">
                <div class="PublicationTitle">
                    <a href="/DocumentViewer/en/house-debate/789">Hansard - 003</a>
                    <div class="PublicationDate">2024-01-04</div>
                </div>
                <div class="PublicationHeaderButtons">
                    <a href="/Content/House/441/Debates/004/HAN004-E.PDF">PDF</a>
                </div>
            </div>
        </div>
        """
        empty_page = "<div id=\"Publications\"></div>"

        with patch(
            "parliament.imports.publicationsearch_provider.fetch_with_backoff",
            side_effect=[
                _HttpResponseMock(page_one),
                _HttpResponseMock(page_two),
                _HttpResponseMock(empty_page),
            ],
        ) as mock_fetch:
            results = list(
                self.client.search_debates(parliament=44, session=1, page_size=15)
            )

        self.assertEqual(len(results), 3)
        ids = [result.publication_id for result in results]
        self.assertEqual(ids, [123, 456, 789])
        self.assertTrue(all(result.english_pdf_url for result in results))
        self.assertEqual(mock_fetch.call_count, 3)

    def test_invalid_page_size_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            list(self.client.search_debates(parliament=44, session=1, page_size=17))


@dataclass
class _StubClient:
    payload: Iterable[PublicationSearchResult]

    def search_debates(self, *, parliament: int, session: int) -> Iterable[PublicationSearchResult]:
        return list(self.payload)


class PublicationSearchDebateProviderTests(TestCase):
    def setUp(self) -> None:
        self.session = Session.objects.create(
            id="45-1",
            name="45th Parliament, 1st Session",
            start=datetime.date(2024, 1, 1),
            parliamentnum=45,
            sessnum=1,
        )

    def test_iter_new_debates_filters_existing_and_missing_xml(self) -> None:
        Document.objects.create(
            document_type=Document.DEBATE,
            session=self.session,
            source_id=200,
            number="200",
        )

        results: List[PublicationSearchResult] = [
            PublicationSearchResult(
                publication_id=100,
                parliament=45,
                session=1,
                issue="Hansard - 001",
                issue_code="001",
                english_html_url="https://example.com/en/100",
                french_html_url="https://example.com/fr/100",
                english_pdf_url="https://example.com/HAN001-E.PDF",
                french_pdf_url="https://example.com/HAN001-F.PDF",
                publication_date="2024-01-10",
            ),
            PublicationSearchResult(
                publication_id=200,
                parliament=45,
                session=1,
                issue="Hansard - 002",
                issue_code="002",
                english_html_url="https://example.com/en/200",
                french_html_url="https://example.com/fr/200",
                english_pdf_url="https://example.com/HAN002-E.PDF",
                french_pdf_url="https://example.com/HAN002-F.PDF",
                publication_date="2024-01-11",
            ),
            PublicationSearchResult(
                publication_id=300,
                parliament=45,
                session=1,
                issue="Hansard - Missing",
                issue_code=None,
                english_html_url="https://example.com/en/300",
                french_html_url="https://example.com/fr/300",
                english_pdf_url=None,
                french_pdf_url=None,
                publication_date="2024-01-12",
            ),
        ]

        provider = PublicationSearchDebateProvider(_StubClient(results))
        debates = list(provider.iter_new_debates(self.session))

        self.assertEqual(len(debates), 1)
        debate = debates[0]
        self.assertEqual(debate.source_id, 100)
        self.assertEqual(debate.number, "1")
        self.assertIn("HAN001-E.XML", debate.english_xml_url)
        self.assertIn("HAN001-F.XML", debate.french_xml_url)