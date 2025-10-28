from __future__ import annotations

from dataclasses import dataclass

from django.db.models import OuterRef, Subquery
from django.utils.functional import cached_property

from parliament.bills.models import Bill, VoteQuestion
from parliament.committees.models import Committee, CommitteeMeeting
from parliament.core.models import ElectedMember, Session
from parliament.hansards.models import Document

from .serializers import (
    BillListPayload,
    CommitteeListPayload,
    DebateListPayload,
    PoliticianListPayload,
    VoteListPayload,
    serialize_bill_list_filters,
    serialize_bill_list_item,
    serialize_committee_list_item,
    serialize_debate_list_item,
    serialize_politician_list_item,
    serialize_vote_list_filters,
    serialize_vote_list_item,
)


# MARK: Bill list


@dataclass
class BillListPayloadBuilder:
    session_id: str | None = None
    limit: int = 50

    def build(self) -> BillListPayload:
        return {
            "filters": serialize_bill_list_filters(self._sessions, self._normalized_session),
            "items": [serialize_bill_list_item(bill) for bill in self._bills],
        }

    # MARK: Private helpers

    @cached_property
    def _sessions(self) -> list[Session]:
        return list(Session.objects.with_bills().order_by("-start"))

    @cached_property
    def _normalized_session(self) -> str | None:
        if not self.session_id:
            return None
        valid_ids = {session.id for session in self._sessions}
        return self.session_id if self.session_id in valid_ids else None

    @cached_property
    def _bills(self) -> list[Bill]:
        queryset = (
            Bill.objects.select_related(
                "session",
                "sponsor_politician",
                "sponsor_member",
                "sponsor_member__party",
            )
            .order_by("-latest_debate_date", "-introduced", "-id")
        )
        if self._normalized_session:
            queryset = queryset.filter(session_id=self._normalized_session)
        return list(queryset[: max(1, self.limit)])


# MARK: Politician list


@dataclass
class PoliticianListPayloadBuilder:
    status: str = "current"

    def build(self) -> PoliticianListPayload:
        return {
            "items": [serialize_politician_list_item(member) for member in self._members],
        }

    # MARK: Private helpers

    @cached_property
    def _members(self) -> list[ElectedMember]:
        queryset = ElectedMember.objects.select_related(
            "politician",
            "party",
            "riding",
        )
        if self.status == "current":
            queryset = queryset.filter(end_date__isnull=True)
        elif self.status == "former":
            queryset = queryset.filter(end_date__isnull=False)
        return list(queryset.order_by("politician__name"))


# MARK: Debate list


@dataclass
class DebateListPayloadBuilder:
    limit: int = 20

    def build(self) -> DebateListPayload:
        return {
            "items": [serialize_debate_list_item(document) for document in self._documents],
        }

    # MARK: Private helpers

    @cached_property
    def _documents(self) -> list[Document]:
        queryset = Document.debates.filter(
            public=True).select_related("session")
        return list(queryset.order_by("-date", "-number")[: max(1, self.limit)])


# MARK: Committee list


@dataclass
class CommitteeListPayloadBuilder:
    limit: int | None = None

    def build(self) -> CommitteeListPayload:
        committees = self._committees
        latest_meetings = self._latest_meetings_by_committee
        latest_sessions = self._latest_sessions_by_committee
        items = []
        for committee in committees:
            meeting = latest_meetings.get(committee.id)
            session = latest_sessions.get(committee.id)
            items.append(serialize_committee_list_item(
                committee, session, meeting))
        return {"items": items}

    # MARK: Private helpers

    @cached_property
    def _committees(self) -> list[Committee]:
        queryset = Committee.objects.filter(display=True).order_by("name_en")
        if self.limit:
            queryset = queryset[: max(1, self.limit)]
        return list(queryset)

    @cached_property
    def _latest_meetings_by_committee(self) -> dict[int, CommitteeMeeting | None]:
        committees = self._committees
        if not committees:
            return {}
        subquery = CommitteeMeeting.objects.filter(
            committee_id=OuterRef("pk")).order_by("-date", "-number")
        values = (
            Committee.objects.filter(
                id__in=[committee.id for committee in committees])
            .annotate(latest_meeting_id=Subquery(subquery.values("id")[:1]))
            .values("id", "latest_meeting_id")
        )
        meeting_ids = [entry["latest_meeting_id"]
                       for entry in values if entry["latest_meeting_id"]]
        meetings = (
            CommitteeMeeting.objects.filter(id__in=meeting_ids)
            .select_related("committee", "session")
            .order_by("-date", "-number")
        )
        meeting_map = {meeting.id: meeting for meeting in meetings}
        return {
            entry["id"]: meeting_map.get(entry["latest_meeting_id"]) for entry in values
        }

    @cached_property
    def _latest_sessions_by_committee(self) -> dict[int, Session | None]:
        committees = self._committees
        if not committees:
            return {}
        subquery = (
            CommitteeMeeting.objects.filter(committee_id=OuterRef("pk"))
            .order_by("-date", "-number")
            .values("session")[:1]
        )
        values = (
            Committee.objects.filter(
                id__in=[committee.id for committee in committees])
            .annotate(latest_session_id=Subquery(subquery))
            .values("id", "latest_session_id")
        )
        session_ids = [entry["latest_session_id"]
                       for entry in values if entry["latest_session_id"]]
        sessions = Session.objects.filter(id__in=session_ids)
        session_map = {session.id: session for session in sessions}
        return {
            entry["id"]: session_map.get(entry["latest_session_id"]) for entry in values
        }


# MARK: Vote list


@dataclass
class VoteListPayloadBuilder:
    session_id: str | None = None
    limit: int = 100

    def build(self) -> VoteListPayload:
        return {
            "filters": serialize_vote_list_filters(self._sessions, self._normalized_session),
            "items": [serialize_vote_list_item(vote) for vote in self._votes],
        }

    # MARK: Private helpers

    @cached_property
    def _sessions(self) -> list[Session]:
        return list(
            Session.objects.filter(votequestion__isnull=False)
            .distinct()
            .order_by("-start")
        )

    @cached_property
    def _normalized_session(self) -> str | None:
        if not self.session_id:
            return None
        valid_ids = {session.id for session in self._sessions}
        return self.session_id if self.session_id in valid_ids else None

    @cached_property
    def _votes(self) -> list[VoteQuestion]:
        queryset = VoteQuestion.objects.select_related(
            "session", "bill").order_by("-date", "-number")
        if self._normalized_session:
            queryset = queryset.filter(session_id=self._normalized_session)
        return list(queryset[: max(1, self.limit)])
