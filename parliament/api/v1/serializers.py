from __future__ import annotations

from typing import Iterable, NotRequired, TypedDict

from django.conf import settings
from django.utils.html import strip_tags

from parliament.bills.models import Bill, MemberVote, PartyVote, VoteQuestion
from parliament.committees.models import Committee, CommitteeMeeting
from parliament.core.models import ElectedMember, Session, SiteNews
from parliament.hansards.models import Document, Statement
from parliament.text_analysis.models import TextAnalysis
from parliament.summaries.models import Summary
from parliament.rag.models import KnowledgeSource

# MARK: Typed payload contracts


class KnowledgeChunkScopePayload(TypedDict):
    source_type: str
    source_identifier: str


class SessionPayload(TypedDict):
    id: str
    name: str
    parliament: int | None
    session: int | None


class SessionOptionPayload(TypedDict):
    id: str
    label: str


class BillReferencePayload(TypedDict):
    number: str
    session: SessionPayload
    title: str
    short_title: str | None
    url: str
    is_law: bool


class VoteSummaryPayload(TypedDict):
    number: int
    date: str
    description: str
    result: str
    result_code: str
    url: str
    bill_number: str | None
    rag_scope: KnowledgeChunkScopePayload | None


class VoteListItemPayload(TypedDict):
    number: int
    date: str
    description: str
    result: str
    result_code: str
    url: str
    session: SessionPayload
    bill_number: str | None
    bill_url: str | None
    yea_total: int
    nay_total: int
    paired_total: int
    rag_scope: KnowledgeChunkScopePayload | None


class VoteListFiltersPayload(TypedDict):
    sessions: list[SessionOptionPayload]
    selected_session: str | None


class VoteListPayload(TypedDict):
    filters: VoteListFiltersPayload
    items: list[VoteListItemPayload]


class VoteDetailDataPayload(TypedDict):
    number: int
    date: str
    description: str
    result: str
    result_code: str
    url: str
    session: SessionPayload
    yea_total: int
    nay_total: int
    paired_total: int
    bill: BillReferencePayload | None
    context_statement_url: str | None
    rag_scope: KnowledgeChunkScopePayload | None


class PartyVotePayload(TypedDict):
    party_name: str
    party_short: str | None
    vote: str
    vote_code: str
    disagreement: float | None


class MemberBallotPayload(TypedDict):
    politician_name: str
    politician_url: str | None
    party: str | None
    riding: str | None
    vote: str
    vote_code: str
    dissent: bool


class VoteDetailPayload(TypedDict):
    vote: VoteDetailDataPayload
    party_breakdown: list[PartyVotePayload]
    ballots: list[MemberBallotPayload]


class SiteNewsPayload(TypedDict):
    id: int
    title: str
    date: str
    text: str
    html: str


class WordcloudEntryPayload(TypedDict):
    text: str
    score: float


class HansardTopicPayload(TypedDict, total=False):
    slug: str
    heading: str | None
    minutes: int
    wordcount: int
    additional_segments: list[str]
    subheadings: list[dict[str, str]]
    bill_number: str | None
    debate_stage: str | None
    statement_slugs: list[str]


class HansardSummaryPayload(TypedDict):
    title: str
    text: str
    html: str
    generated_at: str
    token_count: int


class HansardPayload(TypedDict):
    id: int
    date: str | None
    number: str | None
    url: str
    most_frequent_word: str | None


class BillListItemPayload(TypedDict):
    number: str
    session: SessionPayload
    title: str
    short_title: str | None
    status: str | None
    status_date: str | None
    url: str
    sponsor_name: str | None
    sponsor_party: str | None


class BillListFiltersPayload(TypedDict):
    sessions: list[SessionOptionPayload]
    selected_session: str | None


class BillListPayload(TypedDict):
    filters: BillListFiltersPayload
    items: list[BillListItemPayload]


class PoliticianListItemPayload(TypedDict):
    name: str
    url: str
    party: str | None
    party_short: str | None
    riding: str | None
    province: str | None
    start_date: str | None
    rag_scope: KnowledgeChunkScopePayload | None


class PoliticianListPayload(TypedDict):
    items: list[PoliticianListItemPayload]


class DebateListItemPayload(TypedDict):
    date: str | None
    number: str | None
    session: SessionPayload
    url: str
    headline: str
    most_frequent_word: str | None
    rag_scope: KnowledgeChunkScopePayload | None


class DebateListPayload(TypedDict):
    items: list[DebateListItemPayload]


class CommitteeMeetingSummaryPayload(TypedDict):
    date: str
    number: int
    url: str | None


class CommitteeListItemPayload(TypedDict):
    name: str
    short_name: str
    url: str
    latest_session: SessionPayload | None
    latest_meeting: CommitteeMeetingSummaryPayload | None
    rag_scope: KnowledgeChunkScopePayload | None


class CommitteeListPayload(TypedDict):
    items: list[CommitteeListItemPayload]


class StatementPayload(TypedDict):
    slug: str
    time: str | None
    heading: str | None
    topic: str | None
    summary: str
    html: str
    url: str
    politician_name: str | None
    politician_url: str | None
    party: str | None
    riding: str | None


class CommitteeMeetingPayload(TypedDict):
    date: str
    number: int
    url: str
    committee: str


class PaginationPayload(TypedDict):
    page: int
    page_count: int
    page_size: int
    total_items: int
    has_next: bool
    has_previous: bool


class DebateTabPayload(TypedDict):
    key: str
    label: str
    has_content: bool


# MARK: Helper serializers


def serialize_session(session: Session) -> SessionPayload:
    return {
        "id": session.id,
        "name": session.name,
        "parliament": session.parliamentnum,
        "session": session.sessnum,
    }


def serialize_session_option(session: Session) -> SessionOptionPayload:
    return {
        "id": session.id,
        "label": session.name,
    }


def _scope_payload(source_type: str, identifier: str | None) -> KnowledgeChunkScopePayload | None:
    if not identifier:
        return None
    return {"source_type": source_type, "source_identifier": identifier}


def _member_scope(member: ElectedMember) -> KnowledgeChunkScopePayload | None:
    politician = getattr(member, "politician", None)
    if not politician or politician is None:
        return None
    base_identifier = politician.slug or (
        str(politician.id) if politician.id else None)
    if not base_identifier:
        return None
    return _scope_payload(KnowledgeSource.MEMBER, f"member:{base_identifier}")


def _committee_scope(committee: Committee) -> KnowledgeChunkScopePayload | None:
    slug = getattr(committee, "slug", None)
    if not slug:
        return None
    return _scope_payload(KnowledgeSource.COMMITTEE, f"committee:{slug}")


def _debate_scope(document: Document) -> KnowledgeChunkScopePayload | None:
    source_id = getattr(document, "source_id", None)
    if not source_id:
        return None
    return _scope_payload(KnowledgeSource.DEBATE, str(source_id))


def _vote_scope(vote: VoteQuestion) -> KnowledgeChunkScopePayload | None:
    if not vote.session_id or not vote.number:
        return None
    identifier = f"vote:{vote.session_id}:{vote.number}"
    return _scope_payload(KnowledgeSource.VOTE, identifier)


def serialize_bill_reference(bill: Bill) -> BillReferencePayload:
    session = serialize_session(bill.session)
    return {
        "number": bill.number,
        "session": session,
        "title": bill.name_en,
        "short_title": bill.short_title_en or None,
        "url": bill.get_absolute_url(),
        "is_law": bool(bill.law),
    }


def serialize_vote_summary(vote: VoteQuestion) -> VoteSummaryPayload:
    return {
        "number": vote.number,
        "date": str(vote.date),
        "description": vote.description_en,
        "result": vote.get_result_display(),
        "result_code": vote.result,
        "url": vote.get_absolute_url(),
        "bill_number": vote.bill.number if vote.bill else None,
        "rag_scope": _vote_scope(vote),
    }


def serialize_vote_list_filters(
    sessions: Iterable[Session],
    selected_session: str | None,
) -> VoteListFiltersPayload:
    options = [serialize_session_option(session) for session in sessions]
    available = {option["id"] for option in options}
    normalized = selected_session if selected_session in available else None
    return {
        "sessions": options,
        "selected_session": normalized,
    }


def serialize_vote_list_item(vote: VoteQuestion) -> VoteListItemPayload:
    return {
        "number": vote.number,
        "date": str(vote.date),
        "description": vote.description_en,
        "result": vote.get_result_display(),
        "result_code": vote.result,
        "url": vote.get_absolute_url(),
        "session": serialize_session(vote.session),
        "bill_number": vote.bill.number if vote.bill else None,
        "bill_url": vote.bill.get_absolute_url() if vote.bill else None,
        "yea_total": vote.yea_total,
        "nay_total": vote.nay_total,
        "paired_total": vote.paired_total,
        "rag_scope": _vote_scope(vote),
    }


def serialize_vote_detail(vote: VoteQuestion) -> VoteDetailDataPayload:
    return {
        "number": vote.number,
        "date": str(vote.date),
        "description": vote.description_en,
        "result": vote.get_result_display(),
        "result_code": vote.result,
        "url": vote.get_absolute_url(),
        "session": serialize_session(vote.session),
        "yea_total": vote.yea_total,
        "nay_total": vote.nay_total,
        "paired_total": vote.paired_total,
        "bill": serialize_bill_reference(vote.bill) if vote.bill else None,
        "context_statement_url": vote.context_statement.get_absolute_url() if vote.context_statement else None,
        "rag_scope": _vote_scope(vote),
    }


def serialize_party_vote(party_vote: PartyVote) -> PartyVotePayload:
    party = party_vote.party
    return {
        "party_name": party.name_en,
        "party_short": party.short_name_en,
        "vote": party_vote.get_vote_display(),
        "vote_code": party_vote.vote,
        "disagreement": party_vote.disagreement,
    }


def serialize_member_ballot(ballot: MemberVote) -> MemberBallotPayload:
    member = ballot.member
    politician = ballot.politician
    party = member.party if member else None
    riding = member.riding if member else None
    return {
        "politician_name": politician.name if politician else None,
        "politician_url": politician.get_absolute_url() if politician else None,
        "party": party.short_name_en if party else None,
        "riding": str(riding) if riding else None,
        "vote": ballot.get_vote_display(),
        "vote_code": ballot.vote,
        "dissent": bool(ballot.dissent),
    }


def serialize_site_news(items: Iterable[SiteNews]) -> list[SiteNewsPayload]:
    payload: list[SiteNewsPayload] = []
    for item in items:
        payload.append(
            {
                "id": item.id,
                "title": item.title,
                "date": item.date.isoformat(),
                "text": item.text,
                "html": str(item.html()),
            }
        )
    return payload


def serialize_wordcloud(document: Document | None) -> list[WordcloudEntryPayload]:
    if not document:
        return []
    analysis = TextAnalysis.objects.filter(
        key=document.get_text_analysis_url(),
        lang=settings.LANGUAGE_CODE,
    ).first()
    if not analysis or analysis.expired or not analysis.probability_data:
        return []
    entries: list[WordcloudEntryPayload] = []
    for entry in analysis.probability_data:
        text = entry.get("text")
        score = entry.get("score")
        if text is None or score is None:
            continue
        entries.append({"text": str(text), "score": float(score)})
    return entries


def serialize_hansard(document: Document) -> HansardPayload:
    return {
        "id": document.id,
        "date": str(document.date) if document.date else None,
        "number": document.number,
        "url": document.get_absolute_url(),
        "most_frequent_word": document.most_frequent_word or None,
    }


def serialize_bill_list_item(bill: Bill) -> BillListItemPayload:
    sponsor = bill.sponsor_politician
    member = bill.sponsor_member
    sponsor_party = None
    if member and member.party:
        sponsor_party = member.party.short_name_en
    return {
        "number": bill.number,
        "session": serialize_session(bill.session),
        "title": bill.name_en,
        "short_title": bill.short_title_en or None,
        "status": bill.status or None,
        "status_date": str(bill.status_date) if bill.status_date else None,
        "url": bill.get_absolute_url(),
        "sponsor_name": sponsor.name if sponsor else None,
        "sponsor_party": sponsor_party,
    }


def serialize_bill_list_filters(
    sessions: Iterable[Session],
    selected_session: str | None,
) -> BillListFiltersPayload:
    options = [serialize_session_option(session) for session in sessions]
    available_ids = {option["id"] for option in options}
    normalized = selected_session if selected_session in available_ids else None
    return {
        "sessions": options,
        "selected_session": normalized,
    }


def serialize_politician_list_item(member: ElectedMember) -> PoliticianListItemPayload:
    politician = member.politician
    riding = member.riding
    party = member.party
    return {
        "name": politician.name,
        "url": politician.get_absolute_url(),
        "party": party.name_en if party else None,
        "party_short": party.short_name_en if party else None,
        "riding": str(riding) if riding else None,
        "province": riding.province if hasattr(riding, "province") else None,
        "start_date": str(member.start_date) if member.start_date else None,
        "rag_scope": _member_scope(member),
    }


def serialize_debate_list_item(document: Document) -> DebateListItemPayload:
    headline = f"Hansard #{document.number}" if document.number else "Hansard"
    if document.date:
        headline = f"{document.date:%B %d, %Y} Hansard"
    return {
        "date": str(document.date) if document.date else None,
        "number": document.number,
        "session": serialize_session(document.session),
        "url": document.get_absolute_url(),
        "headline": headline,
        "most_frequent_word": document.most_frequent_word or None,
        "rag_scope": _debate_scope(document),
    }


def serialize_committee_meeting_summary(
    meeting: CommitteeMeeting | None,
) -> CommitteeMeetingSummaryPayload | None:
    if not meeting:
        return None
    return {
        "date": str(meeting.date),
        "number": meeting.number,
        "url": meeting.get_absolute_url(),
    }


def serialize_committee_list_item(
    committee: Committee,
    latest_session: Session | None,
    latest_meeting: CommitteeMeeting | None,
) -> CommitteeListItemPayload:
    return {
        "name": committee.name_en,
        "short_name": committee.short_name_en,
        "url": committee.get_absolute_url(),
        "latest_session": serialize_session(latest_session) if latest_session else None,
        "latest_meeting": serialize_committee_meeting_summary(latest_meeting),
        "rag_scope": _committee_scope(committee),
    }


def serialize_hansard_topics(topics: Iterable[dict]) -> list[HansardTopicPayload]:
    payload: list[HansardTopicPayload] = []
    for topic in topics:
        subheds = [
            {"label": heading, "slug": slug}
            for heading, slug in topic.get("subheds", [])
        ]
        payload.append(
            {
                "slug": topic.get("slug"),
                "heading": topic.get("display_heading"),
                "minutes": int(topic.get("minutes", 0)),
                "wordcount": int(topic.get("wordcount", 0)),
                "additional_segments": topic.get("other_segments", []),
                "subheadings": subheds,
                "bill_number": topic.get("bill_debated"),
                "debate_stage": topic.get("bill_debate_stage"),
                "statement_slugs": topic.get("all_slugs", []),
            }
        )
    return payload


def serialize_summary(summary: Summary | None) -> HansardSummaryPayload | None:
    if not summary:
        return None
    return {
        "title": summary.get_summary_type_display(),
        "text": summary.summary_text,
        "html": summary.get_html(),
        "generated_at": summary.created.isoformat(),
        "token_count": summary.total_tokens(),
    }


def serialize_statement(statement: Statement) -> StatementPayload:
    member = statement.member
    party = member.party.short_name if member and member.party else None
    riding = str(member.riding) if member and member.riding else None

    html = statement.text_html(language=settings.LANGUAGE_CODE)
    summary_text = strip_tags(html)[:400]

    return {
        "slug": statement.slug or str(statement.sequence),
        "time": statement.time.isoformat() if statement.time else None,
        "heading": statement.h1,
        "topic": statement.h2,
        "summary": summary_text,
        "html": str(html),
        "url": statement.get_absolute_url(),
        "politician_name": statement.politician.name if statement.politician else None,
        "politician_url": statement.politician.get_absolute_url() if statement.politician else None,
        "party": party,
        "riding": riding,
    }


def serialize_committee_meeting(meeting: CommitteeMeeting) -> CommitteeMeetingPayload:
    return {
        "date": str(meeting.date),
        "number": meeting.number,
        "url": meeting.get_absolute_url(),
        "committee": meeting.committee.short_name,
    }


def serialize_pagination(
    page_number: int,
    page_count: int,
    page_size: int,
    total_items: int,
) -> PaginationPayload:
    return {
        "page": page_number,
        "page_count": page_count,
        "page_size": page_size,
        "total_items": total_items,
        "has_next": page_number < page_count,
        "has_previous": page_number > 1,
    }


def serialize_debate_tabs(options: Iterable[tuple[str, str, bool]]) -> list[DebateTabPayload]:
    return [
        {
            "key": key,
            "label": label,
            "has_content": has_content,
        }
        for key, label, has_content in options
    ]
