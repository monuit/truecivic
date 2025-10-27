"""Views for retrieval augmented context."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from parliament.utils.views import JSONView
from src.services.ai.embedding_service import EmbeddingConfig, EmbeddingService
from src.services.rag.jurisdiction import normalize_jurisdiction
from src.services.rag.language import normalize_language
from src.services.rag.retriever import HybridRetriever
from src.services.nia.client import NiaClient, NiaConfig


@dataclass(frozen=True)
class RagRequest:
    """Parsed RAG request from frontend."""

    query: str
    jurisdiction: str
    language: str

    @staticmethod
    def from_payload(payload: dict[str, object]) -> "RagRequest":
        messages = payload.get("messages") or []
        if not isinstance(messages, list) or not messages:
            raise ValueError("messages must be a non-empty list")
        last = messages[-1]
        if not isinstance(last, dict) or "content" not in last:
            raise ValueError("last message must contain content")
        jurisdiction = normalize_jurisdiction(payload.get("jurisdiction"))
        language = normalize_language(payload.get("language"))
        return RagRequest(query=str(last["content"]), jurisdiction=jurisdiction, language=language)


@method_decorator(csrf_exempt, name="dispatch")
class RagContextView(JSONView):
    """Return retrieval-augmented snippets for chat."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):  # type: ignore[override]
        payload = self._parse_body(request)
        rag_request = RagRequest.from_payload(payload)

        try:
            embedding_service = EmbeddingService(EmbeddingConfig.from_env())
        except RuntimeError as exc:
            return JsonResponse({"error": str(exc)}, status=500)

        try:
            retriever = HybridRetriever(embedding_service)
        except RuntimeError as exc:
            return JsonResponse({"error": str(exc)}, status=500)
        chunks = retriever.retrieve(
            rag_request.query,
            rag_request.jurisdiction,
            rag_request.language,
        )

        nia_context = self._nia_context(rag_request.query)

        return JsonResponse(
            {
                "chunks": [self._serialize_chunk(chunk) for chunk in chunks],
                "nia": nia_context,
            }
        )

    # type: ignore[no-any-unimported]
    def _parse_body(self, request) -> dict[str, object]:
        if not request.body:
            return {}
        return json.loads(request.body.decode("utf-8"))

    # type: ignore[no-any-unimported]
    def _serialize_chunk(self, chunk) -> dict[str, object]:
        return {
            "id": chunk.id,
            "title": chunk.title,
            "content": chunk.content,
            "jurisdiction": chunk.jurisdiction,
            "language": chunk.language,
            "score": chunk.score,
        }

    def _nia_context(self, query: str):
        config = NiaConfig.from_env()
        if not config:
            return []
        client = NiaClient(config)
        return list(client.enrich(query))
