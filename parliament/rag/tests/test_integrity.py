"""Tests for embedding integrity verification."""

from __future__ import annotations

from django.test import TestCase

from parliament.rag.models import KnowledgeChunk, KnowledgeSource
from src.services.rag.integrity import EmbeddingIntegrityService, EmbeddingVerificationResult


class DummyEmbeddingService:
    """Test double for embedding generation."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts):  # type: ignore[no-untyped-def]
        batch = list(texts)
        self.calls.append(batch)
        return [[float(index), 1.0 - float(index)] for index, _ in enumerate(batch, start=1)]


class DummyVectorStore:
    """Test double for the vector store wrapper."""

    def __init__(self) -> None:
        self._existing_ids: set[int] = set()
        self.upserts: list[tuple[int, list[float], dict[str, object]]] = []

    # type: ignore[no-untyped-def]
    def upsert(self, *, point_id, vector, payload):
        self._existing_ids.add(int(point_id))
        self.upserts.append((int(point_id), list(vector), dict(payload)))

    def existing_ids(self, ids):  # type: ignore[no-untyped-def]
        return {int(value) for value in ids if int(value) in self._existing_ids}


class EmbeddingIntegrityServiceTests(TestCase):
    """Validate embedding integrity behaviour."""

    def setUp(self) -> None:  # pragma: no cover - Django contract
        self.embedding_service = DummyEmbeddingService()
        self.vector_store = DummyVectorStore()
        self.service = EmbeddingIntegrityService(
            self.embedding_service, self.vector_store)

    def _create_chunk(self, *, has_embedding: bool) -> KnowledgeChunk:
        embedding = [0.1, 0.2] if has_embedding else []
        return KnowledgeChunk.objects.create(
            source_type=KnowledgeSource.BILL,
            source_identifier="bill:test",
            jurisdiction="canada-federal",
            language="en",
            title="Test Chunk",
            content="Body text",
            embedding=embedding,
        )

    def test_reembeds_missing_embeddings(self) -> None:
        chunk = self._create_chunk(has_embedding=False)

        result = self.service.verify_scope(
            jurisdiction="canada-federal", language="en")

        chunk.refresh_from_db()
        self.assertIsInstance(result, EmbeddingVerificationResult)
        self.assertEqual(result.total_chunks, 1)
        self.assertEqual(result.reembedded, 1)
        self.assertEqual(result.reindexed, 0)
        self.assertTrue(chunk.embedding)
        self.assertEqual(len(self.vector_store.upserts), 1)

    def test_reindexes_missing_vectors(self) -> None:
        chunk = self._create_chunk(has_embedding=True)
        # Simulate missing vector store entry by not pre-populating _existing_ids.

        result = self.service.verify_scope(
            jurisdiction="canada-federal", language="en")

        self.assertEqual(result.reembedded, 0)
        self.assertEqual(result.reindexed, 1)
        self.assertEqual({item[0]
                         for item in self.vector_store.upserts}, {chunk.id})

    def test_verified_returns_true_when_no_repairs_needed(self) -> None:
        chunk = self._create_chunk(has_embedding=True)
        # Pretend the vector already exists to avoid reindexing.
        self.vector_store._existing_ids.add(chunk.id)

        result = self.service.verify_scope(
            jurisdiction="canada-federal", language="en")

        self.assertTrue(result.verified)
        self.assertEqual(result.reembedded, 0)
        self.assertEqual(result.reindexed, 0)
