"""Tests for knowledge chunk API views."""

from __future__ import annotations

from django.urls import reverse
from django.test import TestCase

from parliament.rag.models import KnowledgeChunk, KnowledgeSource


class KnowledgeChunkListViewTests(TestCase):
    """Ensure the chunk list endpoint filters and limits correctly."""

    def setUp(self) -> None:  # pragma: no cover - Django contract
        for index in range(3):
            KnowledgeChunk.objects.create(
                source_type=KnowledgeSource.BILL,
                source_identifier="bill:test",
                jurisdiction="canada-federal",
                language="en",
                title=f"Chunk {index}",
                content="Summary",
                embedding=[0.1, 0.2],
            )

    def test_returns_chunks_for_source_identifier(self) -> None:
        url = reverse("rag_chunk_list")
        response = self.client.get(
            url,
            {"source_identifier": "bill:test", "limit": 2},
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["chunks"]), 2)
        self.assertEqual(payload["scope"]["source_identifier"], "bill:test")

    def test_rejects_invalid_limit(self) -> None:
        url = reverse("rag_chunk_list")
        response = self.client.get(url, {"limit": "zero"}, secure=True)

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_rejects_unknown_source_type(self) -> None:
        url = reverse("rag_chunk_list")
        response = self.client.get(
            url, {"source_type": "unknown"}, secure=True)

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())
