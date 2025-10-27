"""Retriever bridging Django metadata with Qdrant vector search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from parliament.rag.models import KnowledgeChunk
from src.services.ai.embedding_service import EmbeddingService
from src.services.rag.vector_store import QdrantConfig, QdrantVectorStore


@dataclass(frozen=True)
class RetrievedChunk:
    """Result chunk with fused scores."""

    id: int
    title: str
    content: str
    jurisdiction: str
    language: str
    score: float


class HybridRetriever:
    """Retrieve contextual snippets via Qdrant-backed similarity."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: QdrantVectorStore | None = None,
    ) -> None:
        self._embedding_service = embedding_service
        self._vector_store = vector_store or QdrantVectorStore(
            QdrantConfig.from_env())

    def retrieve(
        self,
        query: str,
        jurisdiction: str,
        language: str,
        limit: int = 8,
    ) -> Sequence[RetrievedChunk]:
        embedding = self._embedding_service.embed([query])[0]
        points = self._vector_store.search(
            vector=embedding,
            jurisdiction=jurisdiction,
            language=language,
            limit=limit,
        )
        if not points:
            return []

        chunk_ids = [int(point.id) for point in points]
        chunks = KnowledgeChunk.objects.filter(id__in=chunk_ids)
        chunk_map = {chunk.id: chunk for chunk in chunks}

        results: list[RetrievedChunk] = []
        for point in points:
            chunk = chunk_map.get(int(point.id))
            if not chunk:
                continue
            results.append(
                RetrievedChunk(
                    id=chunk.id,
                    title=chunk.title,
                    content=chunk.content,
                    jurisdiction=chunk.jurisdiction,
                    language=chunk.language,
                    score=float(point.score or 0.0),
                )
            )
        return results

    def ids_for_backfill(self, jurisdiction: str, language: str) -> Iterable[int]:
        """Return chunk ids for scheduler backfill operations."""
        return KnowledgeChunk.objects.filter(
            jurisdiction=jurisdiction,
            language=language,
        ).values_list("id", flat=True)
