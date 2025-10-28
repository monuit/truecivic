"""Integration checks for KnowledgeChunk vectors stored in Qdrant."""

from __future__ import annotations

from typing import ClassVar

from django.test import TestCase

from parliament.rag.models import KnowledgeChunk
from src.services.rag.vector_store import QdrantConfig, QdrantVectorStore


class KnowledgeChunkVectorConsistencyTests(TestCase):
    """Verify that every chunk persisted in Postgres has a Qdrant vector."""

    databases = {"default"}
    _qdrant_config: ClassVar[QdrantConfig | None] = None
    _config_error: ClassVar[str | None] = None

    @classmethod
    def setUpClass(cls) -> None:  # pragma: no cover - Django contract
        super().setUpClass()
        try:
            cls._qdrant_config = QdrantConfig.from_env()
            cls._config_error = None
        except RuntimeError as exc:
            cls._qdrant_config = None
            cls._config_error = str(exc)

    def setUp(self) -> None:  # pragma: no cover - Django contract
        super().setUp()
        if self._qdrant_config is None:
            reason = self._config_error or "Qdrant configuration missing"
            self.skipTest(f"Qdrant not configured: {reason}")

        queryset = KnowledgeChunk.objects.order_by(
            "id").values_list("id", flat=True)
        self._chunk_ids = list(queryset)
        if not self._chunk_ids:
            self.skipTest(
                "No KnowledgeChunk records available for verification.")

        self._vector_store = QdrantVectorStore(self._qdrant_config)

    def test_all_chunks_have_vector_records(self) -> None:
        existing_ids = self._vector_store.existing_ids(self._chunk_ids)
        missing_ids = sorted(set(self._chunk_ids) - existing_ids)
        if missing_ids:
            preview_limit = 20
            sample = ", ".join(str(identifier)
                               for identifier in missing_ids[:preview_limit])
            remainder = len(missing_ids) - preview_limit
            overflow_hint = f" … (+{remainder} more)" if remainder > 0 else ""
            self.fail(
                "Qdrant is missing vectors for %s KnowledgeChunk id(s): %s%s. "
                "Re-run the ingestion pipeline or the verify_embeddings command to restore consistency." % (
                    len(missing_ids),
                    sample,
                    overflow_hint,
                )
            )
