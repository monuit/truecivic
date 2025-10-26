"""
SQLAlchemy database models for Parliament Explorer.

ORM models that map to database tables with proper indexing,
constraints, and relationships.

Responsibility: Define database schema and ORM mappings
"""

from datetime import datetime, time
from typing import Optional, List, Dict
import sqlalchemy as sa
from sqlalchemy import (
    String, Integer, DateTime, Boolean, Text, JSON,
    ForeignKey, Index, UniqueConstraint, CheckConstraint,
    PrimaryKeyConstraint, ForeignKeyConstraint
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    """Base class for all ORM models"""
    pass


class BillModel(Base):
    """
    Database model for legislative bills.
    
    Maps to the 'bills' table with proper indexing on natural keys
    and foreign keys for relationships.
    """
    
    __tablename__ = "bills"
    
    # Primary key (auto-increment)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Natural key fields (unique together)
    jurisdiction: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    parliament: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    session: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    
    # Core fields from OpenParliament
    title_en: Mapped[str] = mapped_column(Text, nullable=False)
    title_fr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    short_title_en: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    short_title_fr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    sponsor_politician_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True
    )
    
    sponsor_politician_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )
    
    introduced_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        index=True
    )
    
    law_status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # LEGISinfo enrichment fields
    legisinfo_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        unique=True,
        index=True
    )
    
    legisinfo_status: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )
    
    legisinfo_summary_en: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    legisinfo_summary_fr: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    subject_tags: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True
    )
    
    committee_studies: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True
    )
    
    royal_assent_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        index=True
    )
    
    royal_assent_chapter: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True
    )
    
    related_bill_numbers: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True
    )
    
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True
    )

    # Source tracking
    source_openparliament: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    
    source_legisinfo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    
    # Timestamps
    last_fetched_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True
    )
    
    last_enriched_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Constraints
    __table_args__ = (
        # Natural key uniqueness
        UniqueConstraint(
            'jurisdiction',
            'parliament',
            'session',
            'number',
            name='uq_bill_natural_key'
        ),
        # Composite indexes for common queries
        Index(
            'idx_bill_parliament_session',
            'parliament',
            'session',
            'introduced_date'
        ),
        Index(
            'idx_bill_fetch_timestamp',
            'last_fetched_at',
            'parliament',
            'session'
        ),
        # Check constraints
        CheckConstraint(
            'parliament > 0',
            name='ck_parliament_positive'
        ),
        CheckConstraint(
            'session > 0',
            name='ck_session_positive'
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<BillModel(id={self.id}, "
            f"number={self.number}, "
            f"parliament={self.parliament}, "
            f"session={self.session})>"
        )


class PoliticianModel(Base):
    """
    Database model for politicians (MPs and Senators).
    
    Maps to the 'politicians' table for tracking sponsors and members.
    """
    
    __tablename__ = "politicians"
    
    # Primary key (OpenParliament politician ID)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Basic information
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    given_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    family_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    # Contact information
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Current membership (JSON for flexibility)
    current_party: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    current_riding: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    current_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # All memberships (historical)
    memberships: Mapped[Optional[List[dict]]] = mapped_column(JSON, nullable=True)
    
    # External IDs
    parl_mp_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, unique=True)
    
    # Timestamps
    last_fetched_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Indexes
    __table_args__ = (
        Index('idx_politician_party_riding', 'current_party', 'current_riding'),
        Index('idx_politician_fetch_timestamp', 'last_fetched_at'),
    )
    
    def __repr__(self) -> str:
        return f"<PoliticianModel(id={self.id}, name={self.name})>"


class FetchLogModel(Base):
    """
    Database model for tracking data fetch operations.
    
    Logs all adapter fetch operations for monitoring and debugging.
    """
    
    __tablename__ = "fetch_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Fetch metadata
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # Metrics
    records_attempted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_succeeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_seconds: Mapped[float] = mapped_column(nullable=False)
    
    # Parameters (JSON for flexibility)
    fetch_params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Errors (if any)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[Optional[List[dict]]] = mapped_column(JSON, nullable=True)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True
    )
    
    # Indexes
    __table_args__ = (
        Index('idx_fetch_log_source_status', 'source', 'status', 'created_at'),
        Index('idx_fetch_log_created', 'created_at'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<FetchLogModel(id={self.id}, "
            f"source={self.source}, "
            f"status={self.status})>"
        )


class PartyModel(Base):
    """Database model for political parties."""
    
    __tablename__ = "parties"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    jurisdiction: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    name_fr: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    short_name_en: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    short_name_fr: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    abbreviation: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)  # Hex color
    website_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('jurisdiction', 'name_en', name='uq_party_natural_key'),
    )
    
    def __repr__(self) -> str:
        return f"<PartyModel(id={self.id}, name={self.name_en})>"


class RidingModel(Base):
    """Database model for electoral districts (ridings)."""
    
    __tablename__ = "ridings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    jurisdiction: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    name_fr: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    province: Mapped[Optional[str]] = mapped_column(String(2), nullable=True, index=True)
    riding_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('jurisdiction', 'name_en', name='uq_riding_natural_key'),
    )
    
    def __repr__(self) -> str:
        return f"<RidingModel(id={self.id}, name={self.name_en})>"


class VoteModel(Base):
    """Database model for parliamentary votes."""
    
    __tablename__ = "votes"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    jurisdiction: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    vote_id: Mapped[str] = mapped_column(String(100), nullable=False)
    parliament: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    session: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    vote_number: Mapped[int] = mapped_column(Integer, nullable=False)
    chamber: Mapped[str] = mapped_column(String(50), nullable=False)
    vote_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    vote_description_en: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vote_description_fr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bill_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('bills.id'), nullable=True, index=True)
    result: Mapped[str] = mapped_column(String(50), nullable=False)
    yeas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    nays: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    abstentions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('jurisdiction', 'vote_id', name='uq_vote_natural_key'),
        Index('idx_vote_parliament_session', 'parliament', 'session'),
    )
    
    def __repr__(self) -> str:
        return f"<VoteModel(id={self.id}, vote_id={self.vote_id}, result={self.result})>"


class VoteRecordModel(Base):
    """Database model for individual politician votes."""
    
    __tablename__ = "vote_records"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vote_id: Mapped[int] = mapped_column(Integer, ForeignKey('votes.id'), nullable=False, index=True)
    politician_id: Mapped[int] = mapped_column(Integer, ForeignKey('politicians.id'), nullable=False, index=True)
    vote_position: Mapped[str] = mapped_column(String(20), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('vote_id', 'politician_id', name='uq_vote_record_natural_key'),
    )
    
    def __repr__(self) -> str:
        return f"<VoteRecordModel(id={self.id}, vote_id={self.vote_id}, position={self.vote_position})>"


class CommitteeModel(Base):
    """Database model for parliamentary committees."""
    
    __tablename__ = "committees"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    natural_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    jurisdiction: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    parliament: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    session: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    committee_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    committee_slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    acronym_en: Mapped[str] = mapped_column(String(50), nullable=False)
    acronym_fr: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_slug: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    name_fr: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    short_name_en: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    short_name_fr: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    chamber: Mapped[str] = mapped_column(String(50), nullable=False)
    parent_committee: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    committee_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    website_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('jurisdiction', 'committee_code', name='uq_committee_natural_key'),
        UniqueConstraint('committee_slug', name='uq_committee_slug'),
        UniqueConstraint('jurisdiction', 'acronym_en', name='uq_committee_acronym'),
        Index('idx_committee_slug', 'committee_slug'),
        Index('idx_committee_acronym', 'jurisdiction', 'acronym_en'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<CommitteeModel(id={self.id}, natural_id={self.natural_id}, "
            f"slug={self.committee_slug}, code={self.committee_code})>"
        )


class DebateModel(Base):
    """Database model for parliamentary debates (Hansard)."""
    
    __tablename__ = "debates"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    jurisdiction: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    hansard_id: Mapped[str] = mapped_column(String(100), nullable=False)
    parliament: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    session: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sitting_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    chamber: Mapped[str] = mapped_column(String(50), nullable=False)
    debate_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    document_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('jurisdiction', 'hansard_id', name='uq_debate_natural_key'),
        Index('idx_debate_parliament_session', 'parliament', 'session'),
    )
    
    def __repr__(self) -> str:
        return f"<DebateModel(id={self.id}, hansard_id={self.hansard_id})>"


class SpeechModel(Base):
    """Database model for individual speeches in debates."""
    
    __tablename__ = "speeches"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    debate_id: Mapped[int] = mapped_column(Integer, ForeignKey('debates.id'), nullable=False, index=True)
    politician_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('politicians.id'), nullable=True, index=True)
    speaker_name: Mapped[str] = mapped_column(String(200), nullable=False)
    speaker_display_name: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp_start: Mapped[Optional[time]] = mapped_column(sa.Time(), nullable=True)
    timestamp_end: Mapped[Optional[time]] = mapped_column(sa.Time(), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('debate_id', 'sequence', name='uq_speech_natural_key'),
    )
    
    def __repr__(self) -> str:
        return f"<SpeechModel(id={self.id}, speaker={self.speaker_name})>"


class DocumentModel(Base):
    """Database model for text documents (for embeddings)."""
    
    __tablename__ = "documents"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    jurisdiction: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    language: Mapped[str] = mapped_column(String(2), nullable=False)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('entity_type', 'entity_id', 'content_type', 'language', name='uq_document_natural_key'),
        Index('idx_document_entity', 'entity_type', 'entity_id'),
    )
    
    def __repr__(self) -> str:
        return f"<DocumentModel(id={self.id}, type={self.entity_type})>"


class EmbeddingModel(Base):
    """Database model for vector embeddings."""
    
    __tablename__ = "embeddings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey('documents.id'), nullable=False, index=True)
    chunk_id: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    vector: Mapped[List[float]] = mapped_column(Vector(1536), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('document_id', 'chunk_id', name='uq_embedding_natural_key'),
    )
    
    def __repr__(self) -> str:
        return f"<EmbeddingModel(id={self.id}, document_id={self.document_id})>"


class RankingModel(Base):
    """Database model for entity rankings."""
    
    __tablename__ = "rankings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    jurisdiction: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    score: Mapped[float] = mapped_column(nullable=False, index=True)
    score_breakdown: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('entity_type', 'entity_id', name='uq_ranking_natural_key'),
        Index('idx_ranking_entity', 'entity_type', 'entity_id'),
        Index('idx_ranking_score', 'entity_type', 'score'),
    )
    
    def __repr__(self) -> str:
        return f"<RankingModel(id={self.id}, type={self.entity_type}, score={self.score})>"


class IgnoredBillModel(Base):
    """Database model for bills ignored by anonymous users."""
    
    __tablename__ = "ignored_bill"
    
    id: Mapped[int] = mapped_column(Integer, autoincrement=True)
    natural_id: Mapped[str] = mapped_column(String(255), nullable=False, comment="Unique identifier for this ignore record")
    jurisdiction: Mapped[str] = mapped_column(String(50), nullable=False, comment="Jurisdiction (e.g., ca-federal)")
    device_id: Mapped[str] = mapped_column(String(255), nullable=False, comment="Anonymous device identifier")
    bill_id: Mapped[int] = mapped_column(Integer, ForeignKey('bills.id', ondelete='CASCADE'), nullable=False, comment="Foreign key to bills.id")
    ignored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    
    __table_args__ = (
        PrimaryKeyConstraint('natural_id', 'jurisdiction', name='pk_ignored_bill'),
        Index('idx_ignored_bill_device', 'device_id', 'jurisdiction'),
        Index('idx_ignored_bill_bill', 'bill_id'),
        Index('idx_ignored_bill_ignored_at', 'ignored_at'),
    )
    
    def __repr__(self) -> str:
        return f"<IgnoredBillModel(id={self.id}, device={self.device_id}, bill={self.bill_id})>"


class PersonalizedFeedTokenModel(Base):
    """Database model for personalized feed tokens."""
    
    __tablename__ = "personalized_feed_token"
    
    id: Mapped[int] = mapped_column(Integer, autoincrement=True)
    natural_id: Mapped[str] = mapped_column(String(255), nullable=False, comment="Token UUID")
    jurisdiction: Mapped[str] = mapped_column(String(50), nullable=False, comment="Jurisdiction (e.g., ca-federal)")
    device_id: Mapped[str] = mapped_column(String(255), nullable=False, comment="Anonymous device identifier")
    token: Mapped[str] = mapped_column(String(255), nullable=False, comment="Unique feed token")
    feed_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="Type: bills, votes, debates, all")
    filters_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="Filter preferences as JSON")
    last_accessed: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="Last time feed was accessed")
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0', comment="Number of accesses")
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    
    __table_args__ = (
        PrimaryKeyConstraint('natural_id', 'jurisdiction', name='pk_personalized_feed_token'),
        UniqueConstraint('token', name='uq_personalized_feed_token_token'),
        Index('idx_feed_token_device', 'device_id', 'jurisdiction'),
        Index('idx_feed_token_token', 'token', unique=True),
        Index('idx_feed_token_last_accessed', 'last_accessed'),
    )
    
    def __repr__(self) -> str:
        return f"<PersonalizedFeedTokenModel(id={self.id}, token={self.token}, type={self.feed_type})>"


class CommitteeMeetingModel(Base):
    """Database model for committee meetings."""
    
    __tablename__ = "committee_meetings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    committee_id: Mapped[int] = mapped_column(Integer, ForeignKey('committees.id', ondelete='CASCADE'), nullable=False, index=True)
    meeting_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parliament: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    session: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    meeting_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    time_of_day: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    title_en: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title_fr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meeting_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    room: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    witnesses: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    documents: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('committee_id', 'meeting_number', 'parliament', 'session', name='uq_committee_meeting_natural_key'),
        Index('idx_committee_meetings_committee_date', 'committee_id', 'meeting_date'),
    )
    
    def __repr__(self) -> str:
        return f"<CommitteeMeetingModel(id={self.id}, committee_id={self.committee_id}, number={self.meeting_number})>"


class APIKeyModel(Base):
    """Database model for API key authentication."""
    
    __tablename__ = "api_keys"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key_hash: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    
    # Rate limiting
    rate_limit_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    rate_limit_window_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
    
    # Metadata
    created_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    
    # Audit
    requests_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    __table_args__ = (
        Index('idx_api_keys_active_expires', 'is_active', 'expires_at'),
    )
    
    def __repr__(self) -> str:
        return f"<APIKeyModel(id={self.id}, name={self.name}, active={self.is_active})>"

