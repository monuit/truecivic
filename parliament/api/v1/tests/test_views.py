from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

from django.http import Http404
from django.test import RequestFactory, TestCase

from parliament.api.v1.views import BillDetailAPIView, HomeAPIView, SearchAPIView
from parliament.bills.models import Bill


class BaseAPIViewTestCase(TestCase):
    """Provides a shared request factory configured for HTTPS calls."""

    def setUp(self) -> None:
        super().setUp()
        self.factory = RequestFactory()

    def _request(self, path: str, params: dict[str, Any] | None = None):
        return self.factory.get(path, data=params or {}, secure=True)


class TestHomeAPIView(BaseAPIViewTestCase):
    @patch("parliament.api.v1.views.HomePayloadBuilder")
    def test_home_view_returns_expected_shape(self, builder_cls) -> None:
        builder_cls.return_value.build.return_value = {
            "latest_hansard": {},
            "hansard_topics": [],
            "site_news": [],
        }

        request = self._request("/api/v1/home/")
        response = HomeAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        builder_cls.assert_called_once()
        self.assertIn("latest_hansard", payload)
        self.assertIn("hansard_topics", payload)
        self.assertIsInstance(payload.get("hansard_topics"), list)
        self.assertIn("site_news", payload)
        self.assertIsInstance(payload.get("site_news"), list)


class TestSearchAPIView(BaseAPIViewTestCase):
    def test_search_requires_query(self) -> None:
        request = self._request("/api/v1/search/")
        response = SearchAPIView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            json.loads(response.content),
            {"error": "Missing required query parameter 'q'."},
        )

    @patch("parliament.api.v1.views.SearchPayloadBuilder")
    def test_search_view_builds_payload(self, builder_cls) -> None:
        builder_instance = builder_cls.return_value
        builder_instance.build.return_value = {
            "query": "housing",
            "normalized_query": "housing",
            "applied_filters": {},
            "sort": None,
            "sort_options": [],
            "pagination": {
                "page": 1,
                "page_count": 1,
                "page_size": 10,
                "total_items": 0,
                "has_next": False,
                "has_previous": False,
            },
            "results": [],
            "facets": {},
            "histogram": {
                "years": [],
                "values": [],
                "discontinuity": None,
            },
        }

        request = self._request(
            "/api/v1/search/",
            {"q": "housing", "page": "3", "sort": "date", "foo": "bar"},
        )
        response = SearchAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        builder_cls.assert_called_once()
        kwargs = builder_cls.call_args.kwargs
        self.assertEqual(kwargs["query"], "housing")
        self.assertEqual(kwargs["page"], 3)
        self.assertEqual(kwargs["sort"], "date")
        params = kwargs["params"]
        self.assertEqual(params["foo"], "bar")
        self.assertNotIn("q", params)
        self.assertNotIn("page", params)
        builder_instance.build.assert_called_once()
        self.assertEqual(json.loads(response.content)["query"], "housing")


class TestBillDetailAPIView(BaseAPIViewTestCase):
    @patch("parliament.api.v1.views.BillDetailPayloadBuilder")
    def test_bill_detail_view_returns_payload(self, builder_cls) -> None:
        sample_payload = {
            "bill": {},
            "similar_bills": [],
            "same_number_bills": [],
            "votes": [],
            "debate": {
                "tabs": [],
                "default_tab": None,
                "active_tab": None,
                "stage_word_counts": {},
                "statements": None,
                "has_mentions": False,
                "has_meetings": False,
            },
            "committee_meetings": [],
        }
        builder_cls.return_value.build.return_value = sample_payload

        request = self._request(
            "/api/v1/bills/43-1/C-1/",
            {"tab": "mentions", "page": "2", "singlepage": "true"},
        )
        response = BillDetailAPIView.as_view()(
            request, session_id="43-1", bill_number="C-1"
        )

        self.assertEqual(response.status_code, 200)
        builder_cls.assert_called_once_with(
            session_id="43-1",
            bill_number="C-1",
            tab="mentions",
            page=2,
            single_page=True,
        )
        builder_cls.return_value.build.assert_called_once()
        self.assertEqual(json.loads(response.content), sample_payload)

    @patch("parliament.api.v1.views.BillDetailPayloadBuilder")
    def test_bill_detail_view_returns_404_when_missing(self, builder_cls) -> None:
        builder_cls.return_value.build.side_effect = Bill.DoesNotExist(
            "missing")

        request = self._request("/api/v1/bills/99-1/Z-99/")
        with self.assertRaises(Http404):
            BillDetailAPIView.as_view()(request, session_id="99-1", bill_number="Z-99")
        builder_cls.assert_called_once_with(
            session_id="99-1",
            bill_number="Z-99",
            tab=None,
            page=1,
            single_page=False,
        )
        builder_cls.return_value.build.assert_called_once()
