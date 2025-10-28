"""Qdrant vector store integration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Iterator, Mapping, Sequence
from urllib.parse import urlparse

try:  # pragma: no cover - optional dependency guard
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels
except ModuleNotFoundError as exc:  # pragma: no cover - exercised in tests
    QdrantClient = None  # type: ignore[assignment]
    qmodels = None  # type: ignore[assignment]
    _QDRANT_IMPORT_ERROR = exc
else:
    _QDRANT_IMPORT_ERROR = None


DEFAULT_HTTP_PORT = 6333
DEFAULT_HTTPS_PORT = 443


@dataclass(frozen=True)
class QdrantConfig:
    """Configuration values for connecting to Qdrant."""

    host: str
    port: int
    use_tls: bool
    api_key: str | None
    collection: str
    timeout_seconds: float

    @property
    def scheme(self) -> str:
        return "https" if self.use_tls else "http"

    @property
    def url(self) -> str:
        default_port = DEFAULT_HTTPS_PORT if self.use_tls else DEFAULT_HTTP_PORT
        if self.port == default_port:
            return f"{self.scheme}://{self.host}"
        return f"{self.scheme}://{self.host}:{self.port}"

    @staticmethod
    def from_env() -> "QdrantConfig":
        raw_url = os.getenv("QDRANT_URL")
        if not raw_url:
            raise RuntimeError("QDRANT_URL must be set to use Qdrant")

        port_override = os.getenv("QDRANT_PORT")
        parsed = urlparse(raw_url if "://" in raw_url else f"http://{raw_url}")
        host = parsed.hostname or parsed.path
        use_tls = (parsed.scheme or "http").lower() == "https"

        if not host:
            raise RuntimeError("QDRANT_URL must include a host")

        if port_override:
            try:
                port = int(port_override)
            except ValueError as exc:  # pragma: no cover - configuration guard
                raise RuntimeError("QDRANT_PORT must be numeric") from exc
        elif parsed.port:
            port = int(parsed.port)
        else:
            port = DEFAULT_HTTPS_PORT if use_tls else DEFAULT_HTTP_PORT

        api_key = os.getenv("QDRANT_API_KEY")
        collection = os.getenv("QDRANT_COLLECTION", "knowledge_chunks")
        timeout_raw = os.getenv("QDRANT_TIMEOUT_SECONDS", "5")
        try:
            timeout = float(timeout_raw)
        except ValueError as exc:  # pragma: no cover - configuration guard
            raise RuntimeError(
                "QDRANT_TIMEOUT_SECONDS must be numeric") from exc

        return QdrantConfig(
            host=host,
            port=port,
            use_tls=use_tls,
            api_key=api_key,
            collection=collection,
            timeout_seconds=timeout,
        )


class QdrantVectorStore:
    """Thin wrapper around the Qdrant client for chunk storage."""

    def __init__(self, config: QdrantConfig) -> None:
        if _QDRANT_IMPORT_ERROR is not None:  # pragma: no cover - defensive guard
            raise RuntimeError(
                "qdrant_client package is required to use QdrantVectorStore"
            ) from _QDRANT_IMPORT_ERROR
        self._collection = config.collection
        self._client = QdrantClient(
            host=config.host,
            port=config.port,
            https=config.use_tls,
            api_key=config.api_key,
            timeout=config.timeout_seconds,
            prefer_grpc=False,
        )

    # MARK: Collection management

    def ensure_collection(self, vector_size: int) -> None:
        """Create the collection if it does not already exist."""
        if self._client.collection_exists(self._collection):
            return
        vectors_config = qmodels.VectorParams(
            size=vector_size,
            distance=qmodels.Distance.COSINE,
        )
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=vectors_config,
        )

    # MARK: Mutation helpers

    def upsert(
        self,
        *,
        point_id: int,
        vector: Sequence[float],
        payload: Mapping[str, object],
    ) -> None:
        self.ensure_collection(len(vector))
        point = qmodels.PointStruct(
            id=point_id,
            vector=list(vector),
            payload=dict(payload),
        )
        self._client.upsert(
            collection_name=self._collection,
            points=[point],
        )

    def delete(self, point_ids: Iterable[int]) -> None:
        ids = list(point_ids)
        if not ids:
            return
        self._client.delete(
            collection_name=self._collection,
            points_selector=qmodels.PointIdsList(points=ids),
        )

    # MARK: Query helpers

    def search(
        self,
        *,
        vector: Sequence[float],
        jurisdiction: str,
        language: str,
        limit: int,
    ) -> list[qmodels.ScoredPoint]:
        if not self._client.collection_exists(self._collection):
            return []
        filters = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="jurisdiction",
                    match=qmodels.MatchValue(value=jurisdiction),
                ),
                qmodels.FieldCondition(
                    key="language",
                    match=qmodels.MatchValue(value=language),
                ),
            ]
        )
        response = self._client.query_points(
            collection_name=self._collection,
            query=list(vector),
            query_filter=filters,
            limit=limit,
            with_payload=True,
        )
        return list(response.points)

    def existing_ids(self, ids: Sequence[int]) -> set[int]:
        """Return the subset of ids that currently exist in the collection."""
        if not ids:
            return set()
        if not self._client.collection_exists(self._collection):
            return set()
        found: set[int] = set()
        for batch in self._batched(ids, 256):
            records = self._client.retrieve(
                collection_name=self._collection,
                ids=list(batch),
                with_vectors=False,
                with_payload=False,
            )
            for record in records:
                try:
                    found.add(int(record.id))
                except (TypeError, ValueError):  # pragma: no cover - defensive cast
                    continue
        return found

    def _batched(self, items: Sequence[int], size: int) -> Iterator[Sequence[int]]:
        for start in range(0, len(items), max(1, size)):
            yield items[start: start + max(1, size)]
