from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .analysis import PROJECT_RE, relevant_component
from .config import settings
from .database import SessionLocal, get_db, init_db
from .extraction import OCR
from .models import (
    Audit, Conflict, ConflictFact, Document, DocumentEntity, Entity, Event, Fact,
    Passage, Relationship, RelationshipEvidence, Workspace,
)
from .processing import ProcessingQueueFull, enqueue, recover_interrupted_jobs, save_upload
from .schemas import (
    AnswerOut, AskRequest, AuditOut, Citation, ConflictOut, ConflictWithFacts,
    DocumentOut, EntityOut, FactOut, GraphOut, HealthOut, Locator, PassageOut,
    RelationshipOut, RelationshipSignals, ReviewUpdate, SearchResult, TimelineEventOut,
    WorkspaceCreate, WorkspaceOut,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("doctrace")


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    recover_interrupted_jobs()
    if settings.seed_default_workspace:
        with SessionLocal() as db:
            existing = db.get(Workspace, settings.seed_default_workspace)
            if not existing:
                db.add(Workspace(id=settings.seed_default_workspace, name="Default workspace"))
                try:
                    db.commit()
                except IntegrityError:
                    db.rollback()
    logger.info("startup similarity_mode=%s ocr_mode=%s", settings.similarity_mode, OCR.mode)
    yield


app = FastAPI(title="DocTrace API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    return response


def _passage(row: Passage) -> PassageOut:
    locator = Locator(page=row.page, paragraph_id=row.paragraph_id, sheet=row.sheet, cell=row.cell)
    highlight = None
    if row.highlight_start is not None and row.highlight_end is not None:
        highlight = (row.highlight_start, row.highlight_end)
    return PassageOut(
        id=row.id, document_id=row.document_id, text=row.text, locator=locator,
        ocr_confidence=row.ocr_confidence, highlight=highlight,
    )


def _relationship(db: Session, row: Relationship) -> RelationshipOut:
    evidence = list(db.scalars(select(RelationshipEvidence.passage_id).where(RelationshipEvidence.relationship_id == row.id)).all())
    return RelationshipOut(
        id=row.id, source_doc_id=row.source_doc_id, target_doc_id=row.target_doc_id, type=row.type,
        score=row.score,
        signals=RelationshipSignals(
            entity_overlap=row.entity_overlap, semantic_similarity=row.semantic_similarity,
            explicit_reference=row.explicit_reference, temporal_context=row.temporal_context,
        ),
        evidence_passage_ids=evidence, review_status=row.review_status,
    )


def _fact(row: Fact) -> FactOut:
    return FactOut.model_validate(row)


def _conflict(db: Session, row: Conflict, with_facts: bool = False):
    fact_ids = list(db.scalars(select(ConflictFact.fact_id).where(ConflictFact.conflict_id == row.id)).all())
    base = dict(
        id=row.id, field=row.field, fact_ids=fact_ids, explanation=row.explanation,
        severity=row.severity, review_status=row.review_status,
    )
    if with_facts:
        facts = db.scalars(select(Fact).where(Fact.id.in_(fact_ids))).all() if fact_ids else []
        return ConflictWithFacts(**base, facts=[_fact(f) for f in facts])
    return ConflictOut(**base)


@app.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(similarity_mode=settings.similarity_mode, ocr_mode=OCR.mode)


@app.get("/workspaces", response_model=list[WorkspaceOut])
def list_workspaces(db: Session = Depends(get_db)):
    return db.scalars(select(Workspace).order_by(Workspace.created_at, Workspace.id)).all()


@app.post("/workspaces", response_model=WorkspaceOut, status_code=201)
def create_workspace(payload: WorkspaceCreate, db: Session = Depends(get_db)):
    row = Workspace(id=_id("ws"), name=payload.name)
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A workspace with this name already exists") from exc
    db.refresh(row)
    return row


@app.post("/workspaces/{workspace_id}/documents", response_model=DocumentOut, status_code=202)
async def upload_document(workspace_id: str, file: UploadFile, db: Session = Depends(get_db)):
    if not db.get(Workspace, workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found")
    doc_id, filename, stored_path, sha256, file_type = await save_upload(file)
    row = Document(
        id=doc_id, workspace_id=workspace_id, filename=filename, stored_path=str(stored_path),
        sha256=sha256, file_type=file_type, status="queued",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    try:
        enqueue(row.id)
    except ProcessingQueueFull as exc:
        db.delete(row)
        db.commit()
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail="Document processing queue is full; try again later") from exc
    return row


@app.get("/workspaces/{workspace_id}/documents", response_model=list[DocumentOut])
def list_documents(workspace_id: str, db: Session = Depends(get_db)):
    if not db.get(Workspace, workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found")
    return db.scalars(select(Document).where(Document.workspace_id == workspace_id).order_by(Document.uploaded_at, Document.id)).all()


@app.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, db: Session = Depends(get_db)):
    row = db.get(Document, document_id)
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    return row


@app.get("/passages/{passage_id}", response_model=PassageOut)
def get_passage(passage_id: str, db: Session = Depends(get_db)):
    row = db.get(Passage, passage_id)
    if not row:
        raise HTTPException(status_code=404, detail="Passage not found")
    return _passage(row)


@app.get("/workspaces/{workspace_id}/passages/search", response_model=list[SearchResult])
def search_passages(
    workspace_id: str,
    q: str = Query(min_length=1, max_length=settings.max_search_chars),
    db: Session = Depends(get_db),
):
    if not db.get(Workspace, workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found")
    rows = db.scalars(select(Passage).join(Document).where(Document.workspace_id == workspace_id, Document.status == "ready")).all()
    terms = {x for x in q.lower().split() if len(x) > 2}
    scored = []
    for row in rows:
        text_terms = set(row.text.lower().split())
        score = len(terms & text_terms) / max(len(terms), 1)
        if q.lower() in row.text.lower():
            score = max(score, 1.0)
        if score > 0:
            scored.append(SearchResult(passage=_passage(row), score=round(score, 6)))
    return sorted(scored, key=lambda x: (-x.score, x.passage.id))[:20]


@app.get("/workspaces/{workspace_id}/graph", response_model=GraphOut)
def get_graph(workspace_id: str, db: Session = Depends(get_db)):
    if not db.get(Workspace, workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found")
    docs = db.scalars(select(Document).where(Document.workspace_id == workspace_id).order_by(Document.uploaded_at, Document.id)).all()
    entities = db.scalars(select(Entity).where(Entity.workspace_id == workspace_id).order_by(Entity.type, Entity.name)).all()
    entity_out = []
    for entity in entities:
        ids = list(db.scalars(select(DocumentEntity.document_id).where(DocumentEntity.entity_id == entity.id).distinct()).all())
        entity_out.append(EntityOut(id=entity.id, type=entity.type, name=entity.name, document_ids=ids))
    relationships = db.scalars(select(Relationship).where(Relationship.workspace_id == workspace_id).order_by(Relationship.score.desc(), Relationship.id)).all()
    return GraphOut(documents=[DocumentOut.model_validate(d) for d in docs], entities=entity_out, relationships=[_relationship(db, r) for r in relationships])


@app.patch("/relationships/{relationship_id}", response_model=RelationshipOut)
def review_relationship(relationship_id: str, payload: ReviewUpdate, db: Session = Depends(get_db)):
    row = db.get(Relationship, relationship_id)
    if not row:
        raise HTTPException(status_code=404, detail="Relationship not found")
    row.review_status = payload.review_status
    db.add(Audit(id=_id("aud"), workspace_id=row.workspace_id, target_type="relationship", target_id=row.id, action=payload.review_status, actor="local-user"))
    db.commit()
    db.refresh(row)
    return _relationship(db, row)


@app.get("/workspaces/{workspace_id}/conflicts", response_model=list[ConflictWithFacts])
def list_conflicts(workspace_id: str, db: Session = Depends(get_db)):
    if not db.get(Workspace, workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found")
    rows = db.scalars(select(Conflict).where(Conflict.workspace_id == workspace_id).order_by(Conflict.field, Conflict.id)).all()
    return [_conflict(db, row, True) for row in rows]


@app.patch("/conflicts/{conflict_id}", response_model=ConflictOut)
def review_conflict(conflict_id: str, payload: ReviewUpdate, db: Session = Depends(get_db)):
    row = db.get(Conflict, conflict_id)
    if not row:
        raise HTTPException(status_code=404, detail="Conflict not found")
    row.review_status = payload.review_status
    db.add(Audit(id=_id("aud"), workspace_id=row.workspace_id, target_type="conflict", target_id=row.id, action=payload.review_status, actor="local-user"))
    db.commit()
    db.refresh(row)
    return _conflict(db, row)


@app.get("/workspaces/{workspace_id}/timeline", response_model=list[TimelineEventOut])
def get_timeline(workspace_id: str, db: Session = Depends(get_db)):
    if not db.get(Workspace, workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found")
    return db.scalars(select(Event).where(Event.workspace_id == workspace_id).order_by(Event.event_date, Event.document_id, Event.id)).all()


@app.post("/workspaces/{workspace_id}/ask", response_model=AnswerOut)
def ask(workspace_id: str, payload: AskRequest, db: Session = Depends(get_db)):
    if not db.get(Workspace, workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found")
    lower = payload.question.lower()
    field = "project_budget" if any(x in lower for x in ("budget", "cost", "fund", "money")) else None
    if field is None and any(x in lower for x in ("deadline", "due", "submission", "submit")):
        field = "submission_deadline"
    component = relevant_component(db, workspace_id, payload.question)
    if field and component:
        facts = db.scalars(select(Fact).where(Fact.workspace_id == workspace_id, Fact.document_id.in_(component), Fact.field == field)).all()
        docs = {d.id: d for d in db.scalars(select(Document).where(Document.id.in_(component))).all()}
        facts = sorted(facts, key=lambda f: (docs[f.document_id].file_date or f.normalized_value, docs[f.document_id].filename, f.id))
        if facts:
            citations: list[Citation] = []
            clauses: list[str] = []
            seen: set[tuple[str, str, str]] = set()
            for fact in facts:
                key = (fact.document_id, fact.normalized_value, fact.status)
                if key in seen:
                    continue
                seen.add(key)
                citations.append(Citation(passage_id=fact.passage_id, document_id=fact.document_id))
                clauses.append(f"{docs[fact.document_id].filename} records {fact.raw_value} as {fact.status} [{len(citations)}]")
            values = {f.normalized_value for f in facts}
            ambiguity = None
            if len(values) > 1:
                ambiguity = "The evidence contains differing values. DocTrace does not decide which value is correct."
            return AnswerOut(text="; ".join(clauses) + ".", citations=citations, ambiguity_note=ambiguity)
    hits = search_passages(workspace_id, payload.question, db)
    if not hits:
        return AnswerOut(text="No extracted passage in this workspace answers that question.", citations=[])
    top = hits[:3]
    return AnswerOut(
        text="The closest evidence appears in " + ", ".join(f"[{i + 1}]" for i in range(len(top))) + ".",
        citations=[Citation(passage_id=hit.passage.id, document_id=hit.passage.document_id) for hit in top],
        ambiguity_note="These are lexical matches; read the cited passages before drawing a conclusion.",
    )


@app.get("/workspaces/{workspace_id}/audit", response_model=list[AuditOut])
def get_audit(workspace_id: str, db: Session = Depends(get_db)):
    if not db.get(Workspace, workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found")
    return db.scalars(select(Audit).where(Audit.workspace_id == workspace_id).order_by(Audit.created_at.desc(), Audit.id)).all()

