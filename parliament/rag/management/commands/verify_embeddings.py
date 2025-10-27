"""Management command to verify persisted embeddings."""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

from src.services.ai.embedding_service import EmbeddingConfig, EmbeddingService
from src.services.rag.integrity import EmbeddingIntegrityService
from src.services.rag.jurisdiction import normalize_jurisdiction
from src.services.rag.language import normalize_language
from src.services.rag.vector_store import QdrantConfig, QdrantVectorStore

logger = logging.getLogger(__name__)


# MARK: Command


class Command(BaseCommand):
    """Verify that each knowledge chunk has an embedding and corresponding vector."""

    help = "Verify knowledge chunk embeddings against the configured vector store"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--jurisdiction",
            default="canada-federal",
            help="Jurisdiction to verify (defaults to canada-federal)",
        )
        parser.add_argument(
            "--language",
            default="en",
            help="Language code to verify (defaults to en)",
        )

    def handle(self, *args, **options):  # type: ignore[override]
        jurisdiction = normalize_jurisdiction(options.get("jurisdiction"))
        language = normalize_language(options.get("language"))
        logger.info("Verifying embeddings for %s/%s", jurisdiction, language)

        try:
            embedding_service = EmbeddingService(EmbeddingConfig.from_env())
        except RuntimeError as exc:
            self.stderr.write(self.style.WARNING(
                f"Skipping verification: {exc}"))
            return

        try:
            vector_store = QdrantVectorStore(QdrantConfig.from_env())
        except RuntimeError as exc:
            self.stderr.write(self.style.WARNING(
                f"Skipping verification: {exc}"))
            return

        service = EmbeddingIntegrityService(embedding_service, vector_store)
        result = service.verify_scope(
            jurisdiction=jurisdiction,
            language=language,
        )

        message = (
            "Verified %(total)s chunks for %(jurisdiction)s/%(language)s. "
            "Reembedded=%(reembedded)s, Reindexed=%(reindexed)s"
        ) % {
            "total": result.total_chunks,
            "jurisdiction": jurisdiction,
            "language": language,
            "reembedded": result.reembedded,
            "reindexed": result.reindexed,
        }

        if result.verified:
            self.stdout.write(self.style.SUCCESS(message))
        else:
            self.stdout.write(message)
