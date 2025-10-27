"""Integrity checks for knowledge chunk embeddings."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterator, Sequence

from django.db import transaction

from parliament.rag.models import KnowledgeChunk
from src.services.ai.embedding_service import EmbeddingService
from src.services.rag.vector_store import QdrantVectorStore

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 32


# MARK: Results


@dataclass(frozen=True)
class EmbeddingVerificationResult:
    """Summary information about an integrity verification run."""

    total_chunks: int
    reembedded: int
    reindexed: int

    @property
    def verified(self) -> bool:
        """Return True if all known chunks have embeddings and vectors."""
        return self.reembedded == 0 and self.reindexed == 0


# MARK: Service


class EmbeddingIntegrityService:
    """Verify and repair persisted embeddings across storage layers."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: QdrantVectorStore,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._batch_size = max(1, batch_size)

    def verify_scope(self, *, jurisdiction: str, language: str) -> EmbeddingVerificationResult:
        """Ensure all chunks in the requested scope have embeddings and vectors."""
        chunks = list(
            KnowledgeChunk.objects.filter(
                jurisdiction=jurisdiction,
                language=language,
            ).order_by("id")
        )
        if not chunks:
            return EmbeddingVerificationResult(0, 0, 0)

        reembedded = self._ensure_embeddings(chunks)
        reindexed = self._ensure_vector_records(chunks)
        result = EmbeddingVerificationResult(
            total_chunks=len(chunks),
            reembedded=reembedded,
            reindexed=reindexed,
        )
        logger.info(
            "Embedding verification complete for %s/%s: %s chunks, %s reembedded, %s reindexed",
            jurisdiction,
            language,
            result.total_chunks,
            result.reembedded,
            result.reindexed,
        )
        return result

    # MARK: Internal helpers

    def _ensure_embeddings(self, chunks: Sequence[KnowledgeChunk]) -> int:
        missing = [chunk for chunk in chunks if not chunk.embedding]
        if not missing:
            return 0

        updated = 0
        for batch in self._batched(missing, self._batch_size):
            texts = [chunk.content for chunk in batch]
            embeddings = self._embedding_service.embed(texts)
            for chunk, embedding in zip(batch, embeddings):
                payload = self._prepare_payload(chunk)
                self._update_chunk_embedding(chunk, embedding)
                self._upsert_vector(chunk.id, embedding, payload)
                updated += 1
        return updated

    def _ensure_vector_records(self, chunks: Sequence[KnowledgeChunk]) -> int:
        ids = [chunk.id for chunk in chunks]
        existing = self._vector_store.existing_ids(ids)
        missing_ids = [
            chunk_id for chunk_id in ids if chunk_id not in existing]
        if not missing_ids:
            return 0

        reindexed = 0
        for chunk in chunks:
            if chunk.id not in missing_ids:
                continue
            if not chunk.embedding:
                logger.warning(
                    "Chunk %s still lacks an embedding; skipping vector upsert", chunk.id)
                continue
            payload = self._prepare_payload(chunk)
            self._upsert_vector(chunk.id, chunk.embedding, payload)
            reindexed += 1
        return reindexed

    def _prepare_payload(self, chunk: KnowledgeChunk) -> dict[str, object]:
        return {
            "source_type": chunk.source_type,
            "source_identifier": chunk.source_identifier,
            "jurisdiction": chunk.jurisdiction,
            "language": chunk.language,
            "title": chunk.title,
        }

    def _update_chunk_embedding(self, chunk: KnowledgeChunk, embedding: Sequence[float]) -> None:
        chunk.embedding = list(embedding)
        with transaction.atomic():
            chunk.save(update_fields=["embedding", "updated_at"])

    def _upsert_vector(
        self,
        chunk_id: int,
        embedding: Sequence[float],
        payload: dict[str, object],
    ) -> None:
        try:
            self._vector_store.upsert(
                point_id=chunk_id,
                vector=embedding,
                payload=payload,
            )
        except Exception as exc:  # pragma: no cover - network contingency
            logger.warning(
                "Failed to upsert chunk %s into vector store: %s", chunk_id, exc)

    def _batched(
        self,
        items: Sequence[KnowledgeChunk],
        batch_size: int,
    ) -> Iterator[Sequence[KnowledgeChunk]]:
        for start in range(0, len(items), batch_size):
            yield items[start: start + batch_size]
