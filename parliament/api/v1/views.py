from __future__ import annotations

from django.http import Http404, HttpRequest, JsonResponse
from django.views import View

from parliament.api.v1.listings import (
    BillListPayloadBuilder,
    CommitteeListPayloadBuilder,
    DebateListPayloadBuilder,
    PoliticianListPayloadBuilder,
    VoteListPayloadBuilder,
)
from parliament.api.v1.services import (
    BillDetailPayloadBuilder,
    HomePayloadBuilder,
    SearchPayloadBuilder,
    VoteDetailPayloadBuilder,
)
from parliament.bills.models import Bill, VoteQuestion


def _coerce_positive_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    try:
        value = int(raw.strip())
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _coerce_bool(raw: str | None) -> bool:
    if raw is None:
        return False
    normalized = raw.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def _coerce_limit(raw: str | None, *, default: int, maximum: int) -> int:
    value = _coerce_positive_int(raw)
    if value is None:
        return default
    return max(1, min(value, maximum))


class HomeAPIView(View):
    """Return structured content for the public homepage."""

    http_method_names = ["get"]

    def get(self, request: HttpRequest) -> JsonResponse:
        payload = HomePayloadBuilder().build()
        return JsonResponse(payload)


class BillDetailAPIView(View):
    """Expose the detailed representation of a bill."""

    http_method_names = ["get"]

    def get(self, request: HttpRequest, session_id: str, bill_number: str) -> JsonResponse:
        tab = request.GET.get("tab")
        page = _coerce_positive_int(request.GET.get("page")) or 1
        single_page = _coerce_bool(request.GET.get("singlepage"))

        try:
            payload = BillDetailPayloadBuilder(
                session_id=session_id,
                bill_number=bill_number,
                tab=tab,
                page=page,
                single_page=single_page,
            ).build()
        except Bill.DoesNotExist as exc:
            raise Http404(str(exc)) from exc

        return JsonResponse(payload)


class SearchAPIView(View):
    """Perform a full-text search across Hansard, bills, and politicians."""

    http_method_names = ["get"]

    def get(self, request: HttpRequest) -> JsonResponse:
        query = request.GET.get("q", "").strip()
        if not query:
            return JsonResponse({"error": "Missing required query parameter 'q'."}, status=400)

        page = _coerce_positive_int(request.GET.get("page")) or 1
        sort = request.GET.get("sort")
        params = request.GET.copy()
        params.pop("q", None)
        params.pop("page", None)

        payload = SearchPayloadBuilder(
            query=query,
            page=page,
            sort=sort,
            params=params,
        ).build()
        return JsonResponse(payload)


class BillListAPIView(View):
    """Return a curated list of bills for discovery views."""

    http_method_names = ["get"]

    def get(self, request: HttpRequest) -> JsonResponse:
        session_id = request.GET.get("session")
        limit = _coerce_limit(request.GET.get(
            "limit"), default=50, maximum=100)
        payload = BillListPayloadBuilder(
            session_id=session_id, limit=limit).build()
        return JsonResponse(payload)


class PoliticianListAPIView(View):
    """Return a list of MPs filtered by status."""

    http_method_names = ["get"]

    def get(self, request: HttpRequest) -> JsonResponse:
        raw_status = request.GET.get("status", "current")
        status = raw_status.strip().lower() if raw_status else "current"
        if status not in {"current", "former"}:
            status = "current"
        payload = PoliticianListPayloadBuilder(status=status).build()
        return JsonResponse(payload)


class DebateListAPIView(View):
    """Expose recent House of Commons debates."""

    http_method_names = ["get"]

    def get(self, request: HttpRequest) -> JsonResponse:
        limit = _coerce_limit(request.GET.get("limit"), default=20, maximum=60)
        payload = DebateListPayloadBuilder(limit=limit).build()
        return JsonResponse(payload)


class CommitteeListAPIView(View):
    """Expose committees with their most recent activity."""

    http_method_names = ["get"]

    def get(self, request: HttpRequest) -> JsonResponse:
        limit = _coerce_positive_int(request.GET.get("limit"))
        payload = CommitteeListPayloadBuilder(limit=limit).build()
        return JsonResponse(payload)


class VoteListAPIView(View):
    """Expose House of Commons votes with optional session filtering."""

    http_method_names = ["get"]

    def get(self, request: HttpRequest) -> JsonResponse:
        session_id = request.GET.get("session")
        limit = _coerce_limit(request.GET.get("limit"),
                              default=100, maximum=250)
        payload = VoteListPayloadBuilder(
            session_id=session_id, limit=limit).build()
        return JsonResponse(payload)


class VoteDetailAPIView(View):
    """Expose the detailed representation of a recorded division."""

    http_method_names = ["get"]

    def get(self, request: HttpRequest, session_id: str, number: str) -> JsonResponse:
        vote_number = _coerce_positive_int(number)
        if not vote_number:
            raise Http404("Invalid vote number")
        try:
            payload = VoteDetailPayloadBuilder(
                session_id=session_id,
                number=vote_number,
            ).build()
        except VoteQuestion.DoesNotExist as exc:
            raise Http404(str(exc)) from exc

        return JsonResponse(payload)
