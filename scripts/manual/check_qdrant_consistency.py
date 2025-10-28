#!/usr/bin/env python3
"""Smoke test to verify KnowledgeChunk vectors exist in Qdrant."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import django  # noqa: E402  (import after path mutation)


# MARK: Configuration helpers


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(levelname)s] %(message)s",
    )


def configure_django(settings_module: str | None) -> None:
    if not settings_module:
        settings_module = "parliament.settings"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
    django.setup()


# MARK: Data structures


@dataclass(frozen=True)
class ConsistencyReport:
    chunk_count: int
    missing_count: int
    missing_ids_preview: list[int]

    @property
    def all_synced(self) -> bool:
        return self.missing_count == 0


# MARK: Core logic


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare KnowledgeChunk records against Qdrant collection entries.",
    )
    parser.add_argument(
        "--jurisdiction",
        help="Filter chunks by jurisdiction (defaults to all)",
    )
    parser.add_argument(
        "--language",
        help="Filter chunks by language (defaults to all)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional maximum number of chunks to verify (0 = no limit)",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=25,
        help="How many missing IDs to display when gaps are found",
    )
    parser.add_argument(
        "--settings",
        help="Optional Django settings module (defaults to parliament.settings)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging output",
    )
    return parser.parse_args(argv)


def gather_chunk_ids(
    *,
    jurisdiction: str | None,
    language: str | None,
    limit: int,
) -> list[int]:
    from parliament.rag.models import KnowledgeChunk

    queryset = KnowledgeChunk.objects.order_by("id")
    if jurisdiction:
        queryset = queryset.filter(jurisdiction=jurisdiction)
    if language:
        queryset = queryset.filter(language=language)
    if limit and limit > 0:
        queryset = queryset[:limit]
    return list(queryset.values_list("id", flat=True))


def build_vector_store():  # type: ignore[no-any-unimported]
    from src.services.rag.vector_store import QdrantConfig, QdrantVectorStore

    config = QdrantConfig.from_env()
    return QdrantVectorStore(config)


def compute_report(
    chunk_ids: list[int],
    *,
    sample_size: int,
):
    vector_store = build_vector_store()
    existing = vector_store.existing_ids(chunk_ids)
    missing = sorted(set(chunk_ids) - existing)
    preview = missing[: max(0, sample_size)] if sample_size > 0 else []
    return ConsistencyReport(
        chunk_count=len(chunk_ids),
        missing_count=len(missing),
        missing_ids_preview=preview,
    )


# MARK: Runner


def main(argv: Iterable[str] | None = None) -> int:
    load_dotenv()
    args = parse_args(argv)
    configure_logging(args.verbose)

    try:
        configure_django(args.settings)
    except Exception as exc:  # pragma: no cover - configuration guard
        logging.error("Failed to configure Django: %s", exc)
        return 2

    chunk_ids = gather_chunk_ids(
        jurisdiction=args.jurisdiction,
        language=args.language,
        limit=args.limit,
    )

    if not chunk_ids:
        logging.warning(
            "No KnowledgeChunk records matched the provided filters.")
        return 0

    logging.info(
        "Checking %s chunk(s) (jurisdiction=%s, language=%s)",
        len(chunk_ids),
        args.jurisdiction or "*",
        args.language or "*",
    )

    try:
        report = compute_report(chunk_ids, sample_size=args.sample_size)
    except RuntimeError as exc:
        logging.error("Unable to construct Qdrant client: %s", exc)
        return 2
    except Exception as exc:  # pragma: no cover - network guard
        logging.error("Failed to query Qdrant: %s", exc)
        return 2

    if report.all_synced:
        logging.info(
            "All %s chunk(s) have matching vectors in Qdrant.", report.chunk_count)
        return 0

    logging.error(
        "Detected %s chunk(s) without vectors in Qdrant (showing up to %s ids): %s",
        report.missing_count,
        len(report.missing_ids_preview),
        ", ".join(str(identifier)
                  for identifier in report.missing_ids_preview) or "<none>",
    )
    logging.error(
        "Re-run the ingestion pipeline or the verify_embeddings management command to repair the gaps.",
    )
    return 1


if __name__ == "__main__":  # pragma: no cover - script entrypoint
    sys.exit(main())
