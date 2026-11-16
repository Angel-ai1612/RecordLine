from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part.capitalize() for part in tail)


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=camel, populate_by_name=True, from_attributes=True)


class WorkspaceCreate(ApiModel):
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Workspace name is required")
        return value


class WorkspaceOut(ApiModel):
    id: str
    name: str
    created_at: datetime


class DocumentOut(ApiModel):
    id: str
    workspace_id: str
    filename: str
    file_type: Literal["pdf", "docx", "xlsx", "image"]
    status: Literal["queued", "extracting", "ocr", "analyzing", "ready", "failed"]
    uploaded_at: datetime
    file_date: date | None


class Locator(ApiModel):
    page: int | None = None
    paragraph_id: str | None = None
    sheet: str | None = None
    cell: str | None = None


class PassageOut(ApiModel):
    id: str
    document_id: str
    text: str
    locator: Locator
    ocr_confidence: float | None = None
    highlight: tuple[int, int] | None = None


class SearchResult(ApiModel):
    passage: PassageOut
    score: float


class EntityOut(ApiModel):
    id: str
    type: Literal["person", "organization", "project", "amount", "date", "item"]
    name: str
    document_ids: list[str]


ReviewStatus = Literal["pending", "confirmed", "rejected"]


class ReviewUpdate(ApiModel):
    review_status: ReviewStatus


class RelationshipSignals(ApiModel):
    entity_overlap: float
    semantic_similarity: float
    explicit_reference: float
    temporal_context: float


class RelationshipOut(ApiModel):
    id: str
    source_doc_id: str
    target_doc_id: str
    type: Literal["revision_of", "references", "supports", "contradicts", "same_topic"]
    score: float
    signals: RelationshipSignals
    evidence_passage_ids: list[str]
    review_status: ReviewStatus


class FactOut(ApiModel):
    id: str
    document_id: str
    passage_id: str
    field: str
    raw_value: str
    normalized_value: str
    unit: str | None
    status: Literal["proposed", "approved", "estimated", "stated"]


class ConflictOut(ApiModel):
    id: str
    field: str
    fact_ids: list[str]
    explanation: str
    severity: Literal["low", "medium", "high"]
    review_status: ReviewStatus


class ConflictWithFacts(ConflictOut):
    facts: list[FactOut]


class TimelineEventOut(ApiModel):
    id: str
    document_id: str
    passage_id: str
    event_date: date
    file_date: date | None
    label: str


class Citation(ApiModel):
    passage_id: str
    document_id: str


class AskRequest(ApiModel):
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question is required")
        return value


class AnswerOut(ApiModel):
    text: str
    citations: list[Citation]
    ambiguity_note: str | None = None


class AuditOut(ApiModel):
    id: str
    workspace_id: str
    target_type: Literal["relationship", "conflict"]
    target_id: str
    action: ReviewStatus
    actor: str
    note: str | None = None
    created_at: datetime


class GraphOut(ApiModel):
    documents: list[DocumentOut]
    entities: list[EntityOut]
    relationships: list[RelationshipOut]


class HealthOut(ApiModel):
    status: Literal["ok"] = "ok"
    similarity_mode: str
    ocr_mode: str

