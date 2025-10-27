"""API views for exposing knowledge chunk summaries."""

from __future__ import annotations

from django.http import JsonResponse

from parliament.rag.models import KnowledgeChunk, KnowledgeSource
from parliament.utils.views import JSONView
from src.services.rag.jurisdiction import normalize_jurisdiction
from src.services.rag.language import normalize_language

DEFAULT_LIMIT = 5
MAX_LIMIT = 25


# MARK: Views


class KnowledgeChunkListView(JSONView):
    """Return knowledge chunks for UI summary experiences."""

    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):  # type: ignore[override]
        try:
            limit = self._parse_limit(request.GET.get("limit"))
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        jurisdiction = normalize_jurisdiction(request.GET.get("jurisdiction"))
        language = normalize_language(request.GET.get("language"))
        source_type = request.GET.get("source_type") or KnowledgeSource.BILL
        if source_type not in KnowledgeSource.values:
            return JsonResponse({"error": "invalid source_type"}, status=400)

        queryset = KnowledgeChunk.objects.filter(
            jurisdiction=jurisdiction,
            language=language,
            source_type=source_type,
        ).order_by("-updated_at")

        source_identifier = request.GET.get("source_identifier")
        if source_identifier:
            queryset = queryset.filter(source_identifier=source_identifier)

        chunks = [self._serialize_chunk(chunk) for chunk in queryset[:limit]]
        return JsonResponse(
            {
                "chunks": chunks,
                "scope": {
                    "jurisdiction": jurisdiction,
                    "language": language,
                    "source_type": source_type,
                    "source_identifier": source_identifier,
                    "limit": limit,
                },
            }
        )

    def _parse_limit(self, raw_limit: str | None) -> int:
        if not raw_limit:
            return DEFAULT_LIMIT
        try:
            limit = int(raw_limit)
        except ValueError as exc:
            raise ValueError("limit must be an integer") from exc
        if limit < 1 or limit > MAX_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
        return limit

    def _serialize_chunk(self, chunk: KnowledgeChunk) -> dict[str, object]:
        return {
            "id": chunk.id,
            "title": chunk.title,
            "content": chunk.content,
            "source_type": chunk.source_type,
            "source_identifier": chunk.source_identifier,
            "jurisdiction": chunk.jurisdiction,
            "language": chunk.language,
            "updated_at": chunk.updated_at.isoformat(),
        }
