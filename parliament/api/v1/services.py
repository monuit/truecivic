from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, TypedDict

from django.core.paginator import Page
from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.utils.functional import cached_property

from parliament.bills.models import Bill, MemberVote, PartyVote, VoteQuestion
from parliament.committees.models import CommitteeMeeting
from parliament.core.models import Session, SiteNews
from parliament.core.views import get_hansard_sections_or_summary
from parliament.hansards.models import Document, Statement
from parliament.summaries.models import Summary
from parliament.rag.models import KnowledgeSource

from parliament.api.v1.serializers import (
    BillReferencePayload,
    KnowledgeChunkScopePayload,
    CommitteeMeetingPayload,
    DebateTabPayload,
    HansardPayload,
    HansardSummaryPayload,
    HansardTopicPayload,
    PaginationPayload,
    SessionPayload,
    SiteNewsPayload,
    StatementPayload,
    VoteSummaryPayload,
    MemberBallotPayload,
    PartyVotePayload,
    VoteDetailPayload,
    VoteDetailDataPayload,
    VoteListPayload,
    VoteListItemPayload,
    VoteListFiltersPayload,
    serialize_bill_reference,
    serialize_committee_meeting,
    serialize_debate_tabs,
    serialize_hansard,
    serialize_hansard_topics,
    serialize_pagination,
    serialize_session,
    serialize_site_news,
    serialize_statement,
    serialize_summary,
    serialize_vote_summary,
    serialize_wordcloud,
    serialize_vote_detail,
    serialize_vote_list_item,
    serialize_vote_list_filters,
    serialize_party_vote,
    serialize_member_ballot,
)
from parliament.search.solr import SearchQuery
from parliament.search.views import PER_PAGE
from parliament.search.utils import SearchPaginator

# MARK: Search sort labels

SORT_LABELS: dict[str, str] = {
    "score desc": "Best match",
    "date desc": "Newest first",
    "date asc": "Oldest first",
}

# MARK: Payload TypedDicts


class HomePayload(TypedDict):
    latest_hansard: HansardPayload | None
    hansard_topics: list[HansardTopicPayload]
    hansard_summary: HansardSummaryPayload | None
    wordcloud: list[dict[str, float | str]]
    recently_debated_bills: list[BillReferencePayload]
    recent_votes: list[VoteSummaryPayload]
    site_news: list[SiteNewsPayload]


class BillDetailDataPayload(TypedDict):
    number: str
    session: SessionPayload
    title: str
    short_title: str | None
    status: str | None
    status_code: str | None
    status_date: str | None
    is_law: bool
    is_private_members_bill: bool
    chamber: str | None
    sponsor_name: str | None
    sponsor_url: str | None
    sponsor_party: str | None
    sponsor_riding: str | None
    summary_html: str | None
    has_library_summary: bool
    library_summary_url: str | None
    rag_scope: KnowledgeChunkScopePayload | None


class StatementListingPayload(TypedDict):
    tab: str
    items: list[StatementPayload]
    pagination: PaginationPayload | None


class BillDebatePayload(TypedDict):
    tabs: list[DebateTabPayload]
    default_tab: str | None
    active_tab: str | None
    stage_word_counts: dict[str, int]
    statements: StatementListingPayload | None
    has_mentions: bool
    has_meetings: bool


class BillDetailPayload(TypedDict):
    bill: BillDetailDataPayload
    similar_bills: list[BillReferencePayload]
    same_number_bills: list[BillReferencePayload]
    votes: list[VoteSummaryPayload]
    debate: BillDebatePayload
    committee_meetings: list[CommitteeMeetingPayload]


class HistogramPayload(TypedDict):
    years: list[int]
    values: list[int]
    discontinuity: int | None


class FacetEntryPayload(TypedDict):
    value: str
    count: int


class SearchResultPayload(TypedDict):
    type: str
    title: str
    url: str
    summary: str
    date: str | None
    meta: dict[str, Any]


class SortOptionPayload(TypedDict):
    value: str
    label: str


class SearchPayload(TypedDict):
    query: str
    normalized_query: str
    applied_filters: dict[str, str]
    sort: str | None
    sort_options: list[SortOptionPayload]
    pagination: PaginationPayload
    results: list[SearchResultPayload]
    facets: dict[str, list[FacetEntryPayload]]
    histogram: HistogramPayload


# MARK: Home builder


@dataclass
class HomePayloadBuilder:
    def build(self) -> HomePayload:
        latest_hansard = self._latest_hansard
        topics, summary = self._topics_and_summary(latest_hansard)
        return {
            "latest_hansard": serialize_hansard(latest_hansard) if latest_hansard else None,
            "hansard_topics": serialize_hansard_topics(topics),
            "hansard_summary": serialize_summary(summary),
            "wordcloud": serialize_wordcloud(latest_hansard),
            "recently_debated_bills": [serialize_bill_reference(bill) for bill in self._recent_bills],
            "recent_votes": [serialize_vote_summary(vote) for vote in self._recent_votes],
            "site_news": serialize_site_news(self._site_news),
        }

    # MARK: Private helpers

    @cached_property
    def _latest_hansard(self) -> Document | None:
        return (
            Document.debates.filter(date__isnull=False, public=True)
            .select_related("session")
            .first()
        )

    def _topics_and_summary(self, hansard: Document | None) -> tuple[list[dict], Summary | None]:
        if not hansard:
            return ([], None)
        return get_hansard_sections_or_summary(hansard)

    @cached_property
    def _recent_bills(self) -> list[Bill]:
        qs = (
            Bill.objects.filter(latest_debate_date__isnull=False)
            .select_related("session")
            .order_by("-latest_debate_date")
        )
        return list(qs[:6])

    @cached_property
    def _current_session(self) -> Session | None:
        try:
            return Session.objects.current()
        except Session.DoesNotExist:
            return None

    @cached_property
    def _recent_votes(self) -> list[VoteQuestion]:
        session = self._current_session
        if not session:
            return []
        qs = (
            VoteQuestion.objects.filter(session=session)
            .select_related("bill")
            .order_by("-date", "-number")
        )
        return list(qs[:6])

    @cached_property
    def _site_news(self) -> Iterable[SiteNews]:
        return SiteNews.public.filter().order_by("-date")[:6]


# MARK: Bill detail builder


@dataclass
class BillDetailPayloadBuilder:
    session_id: str
    bill_number: str
    tab: str | None = None
    page: int = 1
    single_page: bool = False

    def build(self) -> BillDetailPayload:
        bill = self._bill
        debate = self._build_debate_payload(bill)
        return {
            "bill": self._serialize_bill(bill),
            "similar_bills": [serialize_bill_reference(b) for b in self._similar_bills],
            "same_number_bills": [serialize_bill_reference(b) for b in self._same_number_bills],
            "votes": [serialize_vote_summary(v) for v in self._votes],
            "debate": debate,
            "committee_meetings": [serialize_committee_meeting(m) for m in self._meetings],
        }

    # MARK: Private helpers

    @cached_property
    def _bill(self) -> Bill:
        return (
            Bill.objects.select_related(
                "session",
                "sponsor_politician",
                "sponsor_member",
                "sponsor_member__party",
                "sponsor_member__riding",
            )
            .get(session=self.session_id, number=self.bill_number)
        )

    def _serialize_bill(self, bill: Bill) -> BillDetailDataPayload:
        sponsor_member = bill.sponsor_member
        sponsor_party = sponsor_member.party.short_name if sponsor_member and sponsor_member.party else None
        sponsor_riding = str(
            sponsor_member.riding) if sponsor_member and sponsor_member.riding else None
        sponsor_name = bill.sponsor_politician.name if bill.sponsor_politician else None
        sponsor_url = bill.sponsor_politician.get_absolute_url(
        ) if bill.sponsor_politician else None

        payload: BillDetailDataPayload = {
            "number": bill.number,
            "session": serialize_session(bill.session),
            "title": bill.name_en,
            "short_title": bill.short_title_en or None,
            "status": bill.status if bill.status_code else None,
            "status_code": bill.status_code or None,
            "status_date": str(bill.status_date) if bill.status_date else None,
            "is_law": bool(bill.law),
            "is_private_members_bill": bool(bill.privatemember),
            "chamber": bill.get_institution_display() if hasattr(bill, "get_institution_display") else None,
            "sponsor_name": sponsor_name,
            "sponsor_url": sponsor_url,
            "sponsor_party": sponsor_party,
            "sponsor_riding": sponsor_riding,
            "summary_html": bill.get_summary() or None,
            "has_library_summary": bill.library_summary_available,
            "library_summary_url": bill.get_library_summary_url(),
            "rag_scope": None,
        }

        payload["rag_scope"] = self._rag_scope(bill)

        return payload

    def _rag_scope(self, bill: Bill) -> KnowledgeChunkScopePayload | None:
        source_id = bill.legisinfo_id or bill.id
        if not source_id:
            return None
        identifier = f"bill:{source_id}"
        return {
            "source_type": KnowledgeSource.BILL,
            "source_identifier": identifier,
        }

    @cached_property
    def _votes(self) -> list[VoteQuestion]:
        return list(self._bill.votequestion_set.all().order_by("-date", "-number"))

    @cached_property
    def _similar_bills(self) -> list[Bill]:
        return list(
            self._bill.similar_bills.all().select_related(
                "session").order_by("-session_id", "-introduced")[:8]
        )

    @cached_property
    def _same_number_bills(self) -> list[Bill]:
        return list(
            Bill.objects.filter(number=self._bill.number)
            .exclude(id=self._bill.id)
            .select_related("session")
            .order_by("-session_id")[:4]
        )

    @cached_property
    def _meetings(self) -> list[CommitteeMeeting]:
        return list(self._bill.get_committee_meetings().select_related("committee"))

    def _build_debate_payload(self, bill: Bill) -> BillDebatePayload:
        debate_stages = self._debate_stages
        has_mentions = self._mentions.exists()
        has_meetings = bool(self._meetings)
        tabs = self._build_tabs(debate_stages, has_mentions, has_meetings)
        default_tab = self._determine_default_tab(debate_stages, has_mentions)
        active_tab = self._resolve_active_tab(tabs, default_tab)
        statements_payload = self._build_statements_payload(active_tab)

        return {
            "tabs": tabs,
            "default_tab": default_tab,
            "active_tab": active_tab,
            "stage_word_counts": debate_stages,
            "statements": statements_payload,
            "has_mentions": has_mentions,
            "has_meetings": has_meetings,
        }

    @cached_property
    def _debate_stages(self) -> dict[str, int]:
        from django.db.models import Sum

        data = (
            Statement.objects.filter(bill_debated=self._bill, procedural=False)
            .values("bill_debate_stage")
            .annotate(words=Sum("wordcount"))
        )
        return {row["bill_debate_stage"]: row["words"] for row in data if row["words"] and row["words"] > 150}

    @cached_property
    def _mentions(self) -> QuerySet[Statement]:
        return Statement.objects.filter(
            mentioned_bills=self._bill,
            document__document_type=Document.DEBATE,
        ).select_related(
            "member",
            "member__politician",
            "member__party",
            "member__riding",
            "politician",
        ).order_by("-time", "-sequence")

    def _build_tabs(
        self,
        debate_stages: dict[str, int],
        has_mentions: bool,
        has_meetings: bool,
    ) -> list[DebateTabPayload]:
        options: list[tuple[str, str, bool]] = []
        stage_labels = {
            "3": "3rd reading",
            "report": "House debate at report stage",
            "2": "2nd reading",
            "1": "1st reading",
            "senate": "House debate of Senate amendments",
            "other": "House debate (motions & other)",
        }
        for key, label in stage_labels.items():
            options.append((f"stage-{key}", label, key in debate_stages))
        options.append(("mentions", "Other House mentions", has_mentions))
        options.append(("meetings", "Committee meetings", has_meetings))
        return serialize_debate_tabs(options)

    def _determine_default_tab(self, debate_stages: dict[str, int], has_mentions: bool) -> str | None:
        for key in ("3", "2", "1"):
            if key in debate_stages:
                return f"stage-{key}"
        if has_mentions:
            return "mentions"
        if debate_stages:
            first_key = next(iter(debate_stages.keys()))
            return f"stage-{first_key}"
        if self._meetings:
            return "meetings"
        return None

    def _resolve_active_tab(self, tabs: list[DebateTabPayload], default_tab: str | None) -> str | None:
        requested = self.tab
        available = {tab_payload["key"]: tab_payload["has_content"]
                     for tab_payload in tabs}
        if requested and available.get(requested):
            return requested
        if default_tab and available.get(default_tab):
            return default_tab
        for key, has_content in available.items():
            if has_content:
                return key
        return None

    def _build_statements_payload(self, tab: str | None) -> StatementListingPayload | None:
        if not tab:
            return None
        if tab == "meetings":
            return None
        if tab == "mentions":
            page = self._paginate(self._mentions, self._page_size)
            return {
                "items": [serialize_statement(stmt) for stmt in page.object_list],
                "pagination": serialize_pagination(
                    page_number=page.number,
                    page_count=page.paginator.num_pages,
                    page_size=page.paginator.per_page,
                    total_items=page.paginator.count,
                ),
                "tab": tab,
            }
        stage = tab.split("-", 1)[-1]
        if stage not in {"1", "2", "3", "report", "senate", "other"}:
            return None
        qs = self._bill.get_debate_at_stage(stage).select_related(
            "member",
            "member__politician",
            "member__party",
            "member__riding",
            "politician",
        )
        page = self._paginate(qs, self._page_size)
        return {
            "items": [serialize_statement(stmt) for stmt in page.object_list],
            "pagination": serialize_pagination(
                page_number=page.number,
                page_count=page.paginator.num_pages,
                page_size=page.paginator.per_page,
                total_items=page.paginator.count,
            ),
            "tab": tab,
        }

    def _paginate(self, qs: QuerySet[Statement], per_page: int) -> Page:
        paginator = Paginator(qs, per_page)
        try:
            page_number = 1 if self.single_page else max(self.page, 1)
            return paginator.page(page_number)
        except Exception:
            return paginator.page(paginator.num_pages if paginator.num_pages else 1)

    @property
    def _page_size(self) -> int:
        return 500 if self.single_page else 15


# MARK: Search builder


@dataclass
class VoteDetailPayloadBuilder:
    session_id: str
    number: int

    def build(self) -> VoteDetailPayload:
        vote = self._vote
        return {
            "vote": serialize_vote_detail(vote),
            "party_breakdown": [serialize_party_vote(entry) for entry in self._party_votes],
            "ballots": [serialize_member_ballot(ballot) for ballot in self._ballots],
        }

    # MARK: Private helpers

    @cached_property
    def _vote(self) -> VoteQuestion:
        return VoteQuestion.objects.select_related("session", "bill").get(
            session=self.session_id, number=self.number
        )

    @cached_property
    def _party_votes(self) -> list[PartyVote]:
        return list(
            PartyVote.objects.filter(votequestion=self._vote)
            .select_related("party")
            .order_by("party__name_en")
        )

    @cached_property
    def _ballots(self) -> list[MemberVote]:
        return list(
            MemberVote.objects.filter(votequestion=self._vote)
            .select_related("politician", "member", "member__party", "member__riding")
            .order_by("member__party__short_name_en", "politician__name")
        )


@dataclass
class SearchPayloadBuilder:
    query: str
    page: int = 1
    sort: str | None = None
    params: dict[str, Any] | None = None

    def build(self) -> SearchPayload:
        query_string = self.query.strip()
        if not query_string:
            return self._empty_payload()

        start = max(self.page - 1, 0) * PER_PAGE
        query_obj = SearchQuery(
            query_string,
            start=start,
            limit=PER_PAGE,
            user_params=self._user_params,
            facet=True,
        )
        paginator = SearchPaginator(
            query_obj.documents, query_obj.hits, self.page, PER_PAGE)
        selected_sort = self._selected_sort

        return {
            "query": query_string,
            "normalized_query": query_obj.normalized_query,
            "applied_filters": query_obj.filters,
            "sort": selected_sort,
            "sort_options": self._sort_options,
            "pagination": serialize_pagination(
                page_number=paginator.number,
                page_count=paginator.num_pages or 1,
                page_size=PER_PAGE,
                total_items=paginator.hits,
            ),
            "results": [self._serialize_result(doc) for doc in paginator.object_list],
            "facets": self._serialize_facets(query_obj.facet_fields),
            "histogram": {
                "years": [year for year, _ in query_obj.date_counts],
                "values": [count for _, count in query_obj.date_counts],
                "discontinuity": query_obj.discontinuity,
            },
        }

    # MARK: Private helpers

    @property
    def _user_params(self) -> dict[str, Any]:
        params = dict(self.params or {})
        selected_sort = self._selected_sort
        if selected_sort:
            params["sort"] = selected_sort
        return params

    @cached_property
    def _allowed_sort_values(self) -> list[str]:
        return list(SearchQuery.ALLOWABLE_OPTIONS.get("sort", []))

    @cached_property
    def _sort_options(self) -> list[SortOptionPayload]:
        return [{"value": value, "label": self._sort_label(value)} for value in self._allowed_sort_values]

    @property
    def _selected_sort(self) -> str | None:
        sort_value = self.sort or ""
        return sort_value if sort_value in self._allowed_sort_values else None

    @staticmethod
    def _sort_label(value: str) -> str:
        return SORT_LABELS.get(value, value)

    def _serialize_facets(self, facet_fields: dict[str, list[Any]] | None) -> dict[str, list[FacetEntryPayload]]:
        if not facet_fields:
            return {}
        response: dict[str, list[FacetEntryPayload]] = {}
        for key, values in facet_fields.items():
            entries: list[FacetEntryPayload] = []
            for idx in range(0, len(values), 2):
                value = values[idx]
                count = values[idx + 1]
                if count:
                    entries.append({"value": value, "count": int(count)})
            response[key] = entries
        return response

    def _serialize_result(self, document: dict[str, Any]) -> SearchResultPayload:
        doc_type = document.get("django_ct")
        if doc_type == "core.politician":
            return self._serialize_politician_result(document)
        if doc_type == "hansards.statement":
            return self._serialize_statement_result(document)
        if doc_type == "bills.bill":
            return self._serialize_bill_result(document)
        return {
            "type": doc_type or "unknown",
            "title": str(document.get("title") or document.get("text", ""))[:120],
            "url": document.get("url", ""),
            "summary": str(document.get("text", ""))[:320],
            "date": self._extract_date(document),
            "meta": {},
        }

    def _serialize_politician_result(self, document: dict[str, Any]) -> SearchResultPayload:
        name = document.get("politician") or document.get("text", "")
        return {
            "type": "politician",
            "title": name,
            "url": document.get("url", ""),
            "summary": str(document.get("text", ""))[:320],
            "date": None,
            "meta": {
                "party": document.get("party"),
                "riding": document.get("riding"),
            },
        }

    def _serialize_statement_result(self, document: dict[str, Any]) -> SearchResultPayload:
        topic = document.get("topic") or "House debate"
        summary = document.get("text", "")
        return {
            "type": "statement",
            "title": topic,
            "url": document.get("url", ""),
            "summary": summary[:320],
            "date": self._extract_date(document),
            "meta": {
                "politician": document.get("politician"),
                "party": document.get("party"),
                "committee": document.get("committee"),
            },
        }

    def _serialize_bill_result(self, document: dict[str, Any]) -> SearchResultPayload:
        title = document.get("title") or f"Bill {document.get('number', '')}"
        return {
            "type": "bill",
            "title": title,
            "url": document.get("url", ""),
            "summary": str(document.get("text", ""))[:320],
            "date": self._extract_date(document),
            "meta": {
                "number": document.get("number"),
                "session": document.get("session"),
            },
        }

    def _extract_date(self, document: dict[str, Any]) -> str | None:
        date = document.get("date")
        if isinstance(date, str):
            return date
        if hasattr(date, "isoformat"):
            return date.isoformat()
        return None

    def _empty_payload(self) -> SearchPayload:
        return {
            "query": "",
            "normalized_query": "",
            "applied_filters": {},
            "sort": None,
            "sort_options": self._sort_options,
            "pagination": serialize_pagination(1, 1, PER_PAGE, 0),
            "results": [],
            "facets": {},
            "histogram": {"years": [], "values": [], "discontinuity": None},
        }
