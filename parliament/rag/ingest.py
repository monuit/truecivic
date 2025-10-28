"""Utilities for populating RAG knowledge chunks."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Sequence

from django.contrib.postgres.search import SearchVector
from django.db import transaction
from django.db.models import Prefetch
from django.utils.html import strip_tags
from django.utils.text import Truncator

from parliament.bills.models import Bill
from parliament.committees.models import (
    Committee,
    CommitteeActivity,
    CommitteeActivityInSession,
    CommitteeInSession,
    CommitteeMeeting,
)
from parliament.core.models import ElectedMember, Politician
from parliament.elections.models import Candidacy
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
    member_limit: int | None = 50
    committee_limit: int | None = 20
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

    def sync_members(self) -> None:
        """Sync biographies and service records for elected politicians."""
        members_qs = (
            Politician.objects.elected()
            .order_by("name_family", "name_given")
            .prefetch_related(
                Prefetch(
                    "electedmember_set",
                    queryset=ElectedMember.objects.select_related(
                        "party", "riding")
                    .order_by("-start_date"),
                ),
                Prefetch("politicianinfo_set"),
                Prefetch(
                    "candidacy_set",
                    queryset=Candidacy.objects.select_related(
                        "election", "party", "riding"
                    ).order_by("-election__date"),
                ),
            )
        )
        if self._options.member_limit and self._options.member_limit > 0:
            members_qs = members_qs[: self._options.member_limit]
        politicians = list(members_qs)
        if not politicians:
            logger.info("No politicians matched ingestion criteria")
            return
        logger.info(
            "Syncing %s politician profile(s) for %s/%s",
            len(politicians),
            self._options.jurisdiction,
            self._options.language,
        )
        for politician in politicians:
            corpus = self._build_member_corpus(politician)
            if not corpus:
                logger.info(
                    "Skipping politician %s due to empty corpus", politician)
                continue
            identifier = f"member:{politician.slug or politician.id}"
            title = f"{politician.name} profile"
            chunk_total = self._index_chunks(
                source_type=KnowledgeSource.MEMBER,
                source_identifier=identifier,
                base_title=title,
                raw_text=corpus,
            )
            logger.info("Indexed %s chunks for %s",
                        chunk_total, politician.name)

    def sync_committees(self) -> None:
        """Sync descriptive content for parliamentary committees."""
        meetings_prefetch = Prefetch(
            "committeemeeting_set",
            queryset=CommitteeMeeting.objects.select_related(
                "session", "committee")
            .prefetch_related("activities")
            .order_by("-date"),
        )
        activities_prefetch = Prefetch(
            "committeeactivity_set",
            queryset=CommitteeActivity.objects.prefetch_related(
                Prefetch(
                    "committeeactivityinsession_set",
                    queryset=CommitteeActivityInSession.objects.select_related(
                        "session")
                    .order_by("-session__start"),
                )
            ).order_by("name_en"),
        )
        sessions_prefetch = Prefetch(
            "committeeinsession_set",
            queryset=CommitteeInSession.objects.select_related("session")
            .order_by("-session__start"),
        )
        subcommittee_prefetch = Prefetch(
            "subcommittees",
            queryset=Committee.objects.only(
                "id", "name_en", "short_name_en", "slug"),
        )

        committees_qs = (
            Committee.objects.filter(display=True)
            .order_by("name_en")
            .prefetch_related(
                meetings_prefetch,
                activities_prefetch,
                sessions_prefetch,
                subcommittee_prefetch,
            )
        )
        if self._options.committee_limit and self._options.committee_limit > 0:
            committees_qs = committees_qs[: self._options.committee_limit]
        committees = list(committees_qs)
        if not committees:
            logger.info("No committees matched ingestion criteria")
            return
        logger.info(
            "Syncing %s committee profile(s) for %s/%s",
            len(committees),
            self._options.jurisdiction,
            self._options.language,
        )
        for committee in committees:
            corpus = self._build_committee_corpus(committee)
            if not corpus:
                logger.info(
                    "Skipping committee %s due to empty corpus", committee)
                continue
            identifier = f"committee:{committee.slug}"
            title = f"{committee.name_en} overview"
            chunk_total = self._index_chunks(
                source_type=KnowledgeSource.COMMITTEE,
                source_identifier=identifier,
                base_title=title,
                raw_text=corpus,
            )
            logger.info("Indexed %s chunks for %s",
                        chunk_total, committee.name_en)

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

    # MARK: Member ingestion helpers

    def _build_member_corpus(self, politician: Politician) -> str:
        sections = [
            self._member_summary_section(politician),
            self._member_service_section(politician),
            self._member_candidacy_section(politician),
            self._member_info_section(politician),
        ]
        return "\n\n".join(
            segment.strip() for segment in sections if segment and segment.strip()
        )

    def _member_summary_section(self, politician: Politician) -> str:
        members = self._prefetched_members(politician)
        if members:
            latest = members[0]
            tenure = (
                f"since {latest.start_date:%Y-%m-%d}"
                if latest.end_date is None
                else f"from {latest.start_date:%Y-%m-%d} to {latest.end_date:%Y-%m-%d}"
            )
            riding = latest.riding.dashed_name if latest.riding else "an unknown riding"
            party = latest.party.short_name_en if latest.party else "an unknown party"
            status = "currently" if latest.end_date is None else "previously"
            intro = (
                f"{politician.name} {status} serves as Member of Parliament for {riding} "
                f"with the {party} party, {tenure}."
            )
        else:
            # fallback
            intro = f"{politician.name} is a Canadian political figure."
        aliases = self._info_lookup(politician).get("alternate_name", [])
        alias_text = (
            " Alternate names include: " + ", ".join(sorted(set(aliases)))
            if aliases
            else ""
        )
        return (intro + alias_text).strip()

    def _member_service_section(self, politician: Politician) -> str:
        members = self._prefetched_members(politician)
        if not members:
            return ""
        lines: list[str] = ["Parliamentary service history:"]
        for record in members:
            party = record.party.name_en if record.party else "Unknown party"
            riding = record.riding.dashed_name if record.riding else "Unknown riding"
            end_text = "present" if record.end_date is None else f"{record.end_date:%Y-%m-%d}"
            lines.append(
                f"- Served as MP for {riding} with the {party} from {record.start_date:%Y-%m-%d} to {end_text}."
            )
        return "\n".join(lines)

    def _member_candidacy_section(self, politician: Politician) -> str:
        candidacies = self._prefetched_candidacies(politician)
        if not candidacies:
            return ""
        lines = ["Election history:"]
        for candidacy in candidacies:
            elected = "won" if candidacy.elected else "ran"
            party = candidacy.party.name_en if candidacy.party else "Unknown party"
            riding = candidacy.riding.dashed_name if candidacy.riding else "Unknown riding"
            vote_fragment = (
                f" receiving {candidacy.votepercent}% of the vote"
                if candidacy.votepercent is not None
                else ""
            )
            lines.append(
                f"- {elected.capitalize()} in {riding} for the {party} during the {candidacy.election}{vote_fragment}."
            )
        return "\n".join(lines)

    def _member_info_section(self, politician: Politician) -> str:
        info = self._info_lookup(politician)
        if not info:
            return ""
        lines = ["Additional details:"]
        for key in sorted(info):
            if key == "alternate_name":
                continue  # already represented in summary
            values = sorted({value for value in info[key] if value})
            if not values:
                continue
            label = key.replace("_", " ")
            lines.append(f"- {label}: {', '.join(values)}")
        return "\n".join(lines)

    def _prefetched_members(self, politician: Politician) -> list[ElectedMember]:
        manager = getattr(politician, "electedmember_set", None)
        # type: ignore[attr-defined]
        members = list(manager.all()) if manager is not None else []
        if not members:
            members = list(
                politician.electedmember_set.select_related("party", "riding")
                .order_by("-start_date")
            )
        return members

    def _prefetched_candidacies(self, politician: Politician) -> list[Candidacy]:
        manager = getattr(politician, "candidacy_set", None)
        candidacies = list(manager.all()) if manager is not None else [
        ]  # type: ignore[attr-defined]
        if not candidacies:
            candidacies = list(
                politician.candidacy_set.select_related(
                    "election", "party", "riding")
                .order_by("-election__date")
            )
        return candidacies

    def _info_lookup(self, politician: Politician) -> dict[str, list[str]]:
        manager = getattr(politician, "politicianinfo_set", None)
        info_entries = list(manager.all()) if manager is not None else [
        ]  # type: ignore[attr-defined]
        if not info_entries:
            info_entries = list(politician.politicianinfo_set.all())
        lookup: dict[str, list[str]] = {}
        for entry in info_entries:
            cleaned = strip_tags(str(entry.value)).strip()
            if not cleaned:
                continue
            lookup.setdefault(entry.schema, []).append(cleaned)
        return lookup

    # MARK: Committee ingestion helpers

    def _build_committee_corpus(self, committee: Committee) -> str:
        sections = [
            self._committee_summary_section(committee),
            self._committee_sessions_section(committee),
            self._committee_activities_section(committee),
            self._committee_meetings_section(committee),
            self._committee_subcommittees_section(committee),
        ]
        return "\n\n".join(
            segment.strip() for segment in sections if segment and segment.strip()
        )

    def _committee_summary_section(self, committee: Committee) -> str:
        title = committee.name_en or committee.name
        short_name = committee.short_name_en or committee.short_name
        parent = committee.parent.name_en if committee.parent else None
        summary = [
            f"{title} ({short_name}) is a parliamentary committee." if short_name else f"{title} is a parliamentary committee.",
            "It is a joint committee." if committee.joint else "It is a House of Commons committee.",
        ]
        if parent:
            summary.append(f"It reports to the {parent} committee.")
        return " ".join(summary)

    def _committee_sessions_section(self, committee: Committee) -> str:
        manager = getattr(committee, "committeeinsession_set", None)
        # type: ignore[attr-defined]
        sessions = list(manager.all()) if manager is not None else []
        if not sessions:
            sessions = list(
                committee.committeeinsession_set.select_related("session")
                .order_by("-session__start")
            )
        if not sessions:
            return ""
        lines = ["Parliamentary sessions:"]
        for session_link in sessions:
            session = session_link.session
            session_name = session.name if session else str(
                session_link.session_id)
            lines.append(
                f"- {session_name} ({session_link.acronym}) – source: {session_link.get_source_url()}"
            )
        return "\n".join(lines)

    def _committee_activities_section(self, committee: Committee) -> str:
        manager = getattr(committee, "committeeactivity_set", None)
        activities = list(manager.all()) if manager is not None else [
        ]  # type: ignore[attr-defined]
        if not activities:
            activities = list(
                committee.committeeactivity_set.prefetch_related(
                    Prefetch(
                        "committeeactivityinsession_set",
                        queryset=CommitteeActivityInSession.objects.select_related(
                            "session")
                        .order_by("-session__start"),
                    )
                ).order_by("name_en")
            )
        if not activities:
            return ""
        lines = ["Activities and studies:"]
        for activity in activities[:15]:
            label = activity.name_en or activity.name
            activity_type = "study" if activity.study else "activity"
            sessions = ", ".join(
                (
                    link.session.name if link.session else str(link.session_id)
                )
                for link in activity.committeeactivityinsession_set.all()
            )
            session_text = f" (sessions: {sessions})" if sessions else ""
            lines.append(f"- {label} – {activity_type}{session_text}.")
        return "\n".join(lines)

    def _committee_meetings_section(self, committee: Committee) -> str:
        manager = getattr(committee, "committeemeeting_set", None)
        # type: ignore[attr-defined]
        meetings = list(manager.all()) if manager is not None else []
        if not meetings:
            meetings = list(
                committee.committeemeeting_set.select_related("session")
                .prefetch_related("activities")
                .order_by("-date")[:5]
            )
        if not meetings:
            return ""
        lines = ["Recent meetings:"]
        for meeting in meetings[:5]:
            activities = ", ".join(a.name_en for a in meeting.activities.all())
            activity_text = f" covering {activities}" if activities else ""
            camera_text = " in camera" if meeting.in_camera else ""
            lines.append(
                f"- Meeting {meeting.number} on {meeting.date:%Y-%m-%d}{camera_text}{activity_text}."
            )
        return "\n".join(lines)

    def _committee_subcommittees_section(self, committee: Committee) -> str:
        manager = getattr(committee, "subcommittees", None)
        subcommittees = list(manager.all()) if manager is not None else [
        ]  # type: ignore[attr-defined]
        if not subcommittees:
            subcommittees = list(committee.subcommittees.all())
        if not subcommittees:
            return ""
        names = ", ".join(
            sub.short_name_en or sub.name_en for sub in subcommittees)
        return f"Subcommittees: {names}."

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
            member_limit=options.member_limit,
            committee_limit=options.committee_limit,
            chunk_size=options.chunk_size,
        )
