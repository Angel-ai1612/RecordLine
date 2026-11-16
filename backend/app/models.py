from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    documents: Mapped[list["Document"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_workspace_status", "workspace_id", "status"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    file_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    processing_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    processing_warning: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ocr_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    workspace: Mapped[Workspace] = relationship(back_populates="documents")
    passages: Mapped[list["Passage"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Passage(Base):
    __tablename__ = "passages"
    __table_args__ = (UniqueConstraint("document_id", "ordinal"), Index("ix_passages_document", "document_id"))
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer)
    paragraph_id: Mapped[str | None] = mapped_column(String(100))
    sheet: Mapped[str | None] = mapped_column(String(255))
    cell: Mapped[str | None] = mapped_column(String(32))
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    highlight_start: Mapped[int | None] = mapped_column(Integer)
    highlight_end: Mapped[int | None] = mapped_column(Integer)
    document: Mapped[Document] = relationship(back_populates="passages")


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("workspace_id", "type", "name"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class DocumentEntity(Base):
    __tablename__ = "document_entities"
    __table_args__ = (UniqueConstraint("document_id", "entity_id", "passage_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    passage_id: Mapped[str] = mapped_column(ForeignKey("passages.id", ondelete="CASCADE"), nullable=False)
    mention_text: Mapped[str] = mapped_column(String(255), nullable=False)


class Relationship(Base):
    __tablename__ = "relationships"
    __table_args__ = (UniqueConstraint("workspace_id", "source_doc_id", "target_doc_id", "type"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    source_doc_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    target_doc_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    entity_overlap: Mapped[float] = mapped_column(Float, nullable=False)
    semantic_similarity: Mapped[float] = mapped_column(Float, nullable=False)
    explicit_reference: Mapped[float] = mapped_column(Float, nullable=False)
    temporal_context: Mapped[float] = mapped_column(Float, nullable=False)
    review_status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    evidence: Mapped[list["RelationshipEvidence"]] = relationship(cascade="all, delete-orphan")


class RelationshipEvidence(Base):
    __tablename__ = "relationship_evidence"
    __table_args__ = (UniqueConstraint("relationship_id", "passage_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    relationship_id: Mapped[str] = mapped_column(ForeignKey("relationships.id", ondelete="CASCADE"), nullable=False)
    passage_id: Mapped[str] = mapped_column(ForeignKey("passages.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)


class Fact(Base):
    __tablename__ = "facts"
    __table_args__ = (Index("ix_facts_workspace_field", "workspace_id", "field"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    passage_id: Mapped[str] = mapped_column(ForeignKey("passages.id", ondelete="CASCADE"), nullable=False)
    field: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), nullable=False)


class Conflict(Base):
    __tablename__ = "conflicts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    field: Mapped[str] = mapped_column(String(64), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    review_status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    facts: Mapped[list["ConflictFact"]] = relationship(cascade="all, delete-orphan")


class ConflictFact(Base):
    __tablename__ = "conflict_facts"
    __table_args__ = (UniqueConstraint("conflict_id", "fact_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conflict_id: Mapped[str] = mapped_column(ForeignKey("conflicts.id", ondelete="CASCADE"), nullable=False)
    fact_id: Mapped[str] = mapped_column(ForeignKey("facts.id", ondelete="CASCADE"), nullable=False)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_workspace_date", "workspace_id", "event_date"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    passage_id: Mapped[str] = mapped_column(ForeignKey("passages.id", ondelete="CASCADE"), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    file_date: Mapped[date | None] = mapped_column(Date)
    label: Mapped[str] = mapped_column(String(500), nullable=False)


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), default="local-user", nullable=False)
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

