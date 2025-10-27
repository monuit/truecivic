"""Utilities for populating RAG knowledge chunks."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Sequence

from django.contrib.postgres.search import SearchVector
from django.db import transaction
from django.utils.html import strip_tags
from django.utils.text import Truncator

from parliament.bills.models import Bill
from parliament.hansards.models import Document
from parliament.rag.models import KnowledgeChunk, KnowledgeSource
from src.services.ai.embedding_service import EmbeddingService
from src.services.rag.jurisdiction import normalize_jurisdiction
from src.services.rag.language import normalize_language
from src.services.rag.chunker import chunk_text
from src.services.rag.vector_store import QdrantConfig, QdrantVectorStore


logger = logging.getLogger(__name__)

MAX_EMBEDDING_TOKENS = 8000
TOKEN_TO_CHAR_RATIO = 4

__all__ = ["RagIngestor", "IngestOptions"]


# MARK: Configuration

@dataclass(frozen=True)
class IngestOptions:
    """Options for ingestion runs."""

    jurisdiction: str = "canada-federal"
    language: str = "en"
    debate_limit: int = 10
    bill_limit: int = 25
    chunk_size: int = 800


# MARK: Helpers


def _search_config(language: str) -> str:
    if language.lower().startswith("fr"):
        return "french"
    return "english"


def _truncate_title(title: str) -> str:
    return Truncator(title).chars(240)


# MARK: Ingestor


class RagIngestor:
    """Synchronise recorded content into knowledge chunks."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        options: IngestOptions | None = None,
        vector_store: QdrantVectorStore | None = None,
    ) -> None:
        self._embedding_service = embedding_service
        self._options = self._normalize_options(options or IngestOptions())
        self._vector_store = vector_store or QdrantVectorStore(
            QdrantConfig.from_env())

    # MARK: Public API

    def sync_recent_hansards(self) -> None:
        """Top-level wrapper for debate documents."""
        documents = list(
            Document.debates.order_by("-date")[: self._options.debate_limit]
        )
        logger.info(
            "Syncing %s recent hansards for %s/%s",
            len(documents),
            self._options.jurisdiction,
            self._options.language,
        )
        for document in documents:
            body = self._document_body(document)
            if not body:
                logger.info(
                    "Skipping Hansard %s due to empty body",
                    document.id,
                )
                continue
            title = f"Hansard {document.date:%Y-%m-%d} #{document.number}" if document.date else f"Hansard #{document.id}"
            chunk_total = self._index_chunks(
                source_type=KnowledgeSource.DEBATE,
                source_identifier=str(document.source_id),
                base_title=title,
                raw_text=body,
            )
            logger.info("Indexed %s chunks for %s", chunk_total, title)

    def sync_recent_bills(self) -> None:
        """Sync notable bill texts."""
        bills = list(
            Bill.objects.filter(text_docid__isnull=False)
            .exclude(short_title_en="")
            .order_by("-status_date", "-introduced")[: self._options.bill_limit]
        )
        logger.info(
            "Syncing %s recent bills for %s/%s",
            len(bills),
            self._options.jurisdiction,
            self._options.language,
        )
        for bill in bills:
            text = bill.get_text(self._options.language)
            if not text:
                logger.info(
                    "Skipping bill %s due to missing text", bill.number)
                continue
            title = f"Bill {bill.number} – {bill.short_title_en or bill.name_en or bill.name}".strip(
            )
            identifier = f"bill:{bill.legisinfo_id or bill.id}"
            chunk_total = self._index_chunks(
                source_type=KnowledgeSource.BILL,
                source_identifier=identifier,
                base_title=title,
                raw_text=text,
            )
            logger.info("Indexed %s chunks for %s", chunk_total, title)

    # MARK: Internal API

    def _document_body(self, document: Document) -> str:
        statements = document.statement_set.filter(procedural=False)
        field = f"content_{self._options.language}"
        contents = [strip_tags(getattr(statement, field, ""))
                    for statement in statements]
        return "\n\n".join(s for s in contents if s)

    def _index_chunks(
        self,
        *,
        source_type: str,
        source_identifier: str,
        base_title: str,
        raw_text: str,
    ) -> int:
        chunks = list(
            chunk_text(
                base_title,
                raw_text,
                max_length=self._options.chunk_size,
            )
        )
        if not chunks:
            logger.info("No chunks generated for %s", base_title)
            return 0
        prepared_texts = [self._prepare_chunk_text(chunk.text, idx)
                          for idx, chunk in enumerate(chunks, start=1)]
        embeddings = self._embedding_service.embed(prepared_texts)
        for idx, (chunk, embedding, text) in enumerate(
            zip(chunks, embeddings, prepared_texts),
            start=1,
        ):
            chunk_title = _truncate_title(f"{base_title} [{idx}]")
            self._upsert_chunk(
                source_type=source_type,
                source_identifier=source_identifier,
                title=chunk_title,
                content=text,
                embedding=embedding,
            )
        return len(chunks)

    def _prepare_chunk_text(self, text: str, index: int) -> str:
        """Ensure chunk text stays within embedding token limits."""
        # Convert token ceiling to a conservative character limit to avoid exceeding OpenAI limits.
        max_chars = MAX_EMBEDDING_TOKENS * TOKEN_TO_CHAR_RATIO
        if len(text) <= max_chars:
            return text
        truncated = text[:max_chars]
        logger.info(
            "Truncated chunk %s to %s characters to satisfy embedding limits",
            index,
            len(truncated),
        )
        return truncated

    @transaction.atomic
    def _upsert_chunk(
        self,
        *,
        source_type: str,
        source_identifier: str,
        title: str,
        content: str,
        embedding: Sequence[float],
    ) -> None:
        chunk, _ = KnowledgeChunk.objects.update_or_create(
            source_type=source_type,
            source_identifier=source_identifier,
            language=self._options.language,
            jurisdiction=self._options.jurisdiction,
            title=title,
            defaults={
                "content": content,
                "embedding": list(embedding),
            },
        )
        config = _search_config(self._options.language)
        KnowledgeChunk.objects.filter(pk=chunk.pk).update(
            search_document=SearchVector("title", weight="A", config=config)
            + SearchVector("content", weight="B", config=config)
        )
        try:
            self._vector_store.upsert(
                point_id=chunk.pk,
                vector=embedding,
                payload={
                    "source_type": source_type,
                    "source_identifier": source_identifier,
                    "jurisdiction": self._options.jurisdiction,
                    "language": self._options.language,
                    "title": title,
                },
            )
            logger.info("Persisted chunk %s for %s", chunk.pk, title)
        except Exception as exc:  # pragma: no cover - network failure guard
            logger.warning(
                "Failed to upsert chunk %s into Qdrant: %s", chunk.pk, exc)

    def _normalize_options(self, options: IngestOptions) -> IngestOptions:
        return IngestOptions(
            jurisdiction=normalize_jurisdiction(options.jurisdiction),
            language=normalize_language(options.language),
            debate_limit=options.debate_limit,
            bill_limit=options.bill_limit,
            chunk_size=options.chunk_size,
        )
