from __future__ import annotations

import json
import math
import re
import uuid
from collections import defaultdict
from datetime import date, datetime
from itertools import combinations
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .config import BACKEND_DIR
from .models import (
    Conflict,
    ConflictFact,
    Document,
    DocumentEntity,
    Entity,
    Event,
    Fact,
    Passage,
    Relationship,
    RelationshipEvidence,
)


PROJECT_RE = re.compile(r"(?<!NO )(?<!NOT PROJECT )\b[A-Z]{2,8}-\d{4}-\d{1,3}\b")
AMOUNT_RE = re.compile(
    r"(?i)(?:₹|INR|Rs\.?|R[s5][\.:]?|rupees?)\s*([0-9OIl][0-9OIl,]*(?:\.\d+)?)(?:\s*(lakh|lac|k))?"
    r"|([0-9OIl][0-9OIl,]*(?:\.\d+)?)\s*(lakh|lac)\b"
)
MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9,
    "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
DATE_DMY_RE = re.compile(r"\b([0-3]?\d)[/-]([01]?\d)[/-](20\d{2})\b")
DATE_ISO_RE = re.compile(r"\b(20\d{2})-([01]\d)-([0-3]\d)\b")
DATE_WORD_RE = re.compile(
    r"(?i)\b([0-3]?\d)(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(20\d{2})\b|"
    r"\b([A-Za-z]+)\s+([0-3]?\d)(?:st|nd|rd|th)?,?\s+(20\d{2})\b"
)
STATUS_WORDS = {
    "proposed": ("proposed", "requested", "tentative", "suggested", "under discussion", "seeks", "asking", "asked for"),
    "approved": ("approved", "sanctioned", "confirmed", "authorised", "authorized", "accepted"),
    "estimated": ("estimated", "estimate", "forecast", "projected"),
}
FIELD_WORDS = {
    "project_budget": ("budget", "total cost", "allocated funds", "allocation", "sanctioned amount", "grand total"),
    "submission_deadline": ("deadline", "due date", "due-date", "final submission", "submit", "submission date", "approved date"),
}


def uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def normalize_amount(raw: str, scale: str | None = None) -> str | None:
    clean = raw.strip().replace(",", "").replace("O", "0").replace("o", "0")
    clean = clean.replace("I", "1").replace("l", "1")
    try:
        value = float(clean)
    except ValueError:
        return None
    if scale and scale.lower() in {"lakh", "lac"}:
        value *= 100_000
    elif scale and scale.lower() == "k":
        value *= 1_000
    return str(int(round(value)))


def parse_dates(text: str, default_year: int | None = None) -> list[tuple[str, date]]:
    found: list[tuple[str, date]] = []
    for match in DATE_ISO_RE.finditer(text):
        try:
            found.append((match.group(0), date(int(match.group(1)), int(match.group(2)), int(match.group(3)))))
        except ValueError:
            pass
    for match in DATE_DMY_RE.finditer(text):
        try:
            found.append((match.group(0), date(int(match.group(3)), int(match.group(2)), int(match.group(1)))))
        except ValueError:
            pass
    for match in DATE_WORD_RE.finditer(text):
        if match.group(1):
            day, month_text, year = int(match.group(1)), match.group(2), int(match.group(3))
        else:
            month_text, day, year = match.group(4), int(match.group(5)), int(match.group(6))
        month = MONTHS.get(month_text.lower())
        if month:
            try:
                found.append((match.group(0), date(year, month, day)))
            except ValueError:
                pass
    if default_year:
        short = re.compile(r"(?i)\b([0-3]?\d)\s+(" + "|".join(MONTHS) + r")\b(?!\s+20\d{2})")
        for match in short.finditer(text):
            try:
                found.append((match.group(0), date(default_year, MONTHS[match.group(2).lower()], int(match.group(1)))))
            except ValueError:
                pass
    unique: dict[date, str] = {}
    for raw, parsed in found:
        unique.setdefault(parsed, raw)
    return [(raw, parsed) for parsed, raw in unique.items()]


def fact_status(text: str) -> str:
    lower = text.lower()
    for status in ("proposed", "approved", "estimated"):
        if any(word in lower for word in STATUS_WORDS[status]):
            return status
    return "stated"


def _canonical_amount_field(text: str) -> str:
    lower = text.lower()
    if any(word in lower for word in FIELD_WORDS["project_budget"]):
        return "project_budget"
    return "expense_item"


def _entity_type(name: str) -> str:
    if PROJECT_RE.fullmatch(name):
        return "project"
    return "item"


def analyze_document(db: Session, document: Document) -> None:
    db.execute(delete(DocumentEntity).where(DocumentEntity.document_id == document.id))
    db.execute(delete(Fact).where(Fact.document_id == document.id))
    passages = db.scalars(select(Passage).where(Passage.document_id == document.id).order_by(Passage.ordinal)).all()
    document_text = " ".join(p.text for p in passages).lower()
    document_approves_as_submitted = "approved as submitted" in document_text
    is_reporting_document = any(word in document.filename.lower() for word in ("final", "report"))
    for passage in passages:
        text = passage.text
        lower = text.lower()
        for project_id in sorted(set(PROJECT_RE.findall(text.upper()))):
            entity = db.scalar(
                select(Entity).where(
                    Entity.workspace_id == document.workspace_id,
                    Entity.type == "project",
                    Entity.name == project_id,
                )
            )
            if not entity:
                entity = Entity(id=uid("ent"), workspace_id=document.workspace_id, type="project", name=project_id)
                db.add(entity)
                db.flush()
            db.add(DocumentEntity(document_id=document.id, entity_id=entity.id, passage_id=passage.id, mention_text=project_id))

        matches = list(AMOUNT_RE.finditer(text))
        if not matches and re.search(r"(?:^|\|)\s*[A-Z]+\d+=([1-9][0-9]{2,8})(?:\s|$)", text):
            matches = list(re.finditer(r"(?:^|\|)\s*[A-Z]+\d+=([1-9][0-9]{2,8})(?:\s|$)", text))
        for match in matches:
            groups = match.groups()
            raw_number = next((value for index, value in enumerate(groups) if index in {0, 2} and value), match.group(0))
            scale = next((value for index, value in enumerate(groups) if index in {1, 3} and value), None)
            normalized = normalize_amount(raw_number, scale)
            if not normalized:
                continue
            raw = match.group(0)
            field = _canonical_amount_field(text)
            if "summary!" in lower and re.search(r"\btotal\b", lower):
                field = "project_budget"
            local_status = fact_status(text)
            if document_approves_as_submitted and local_status == "stated":
                local_status = "approved"
            if is_reporting_document and local_status == "approved":
                local_status = "stated"
            db.add(
                Fact(
                    id=uid("fact"), workspace_id=document.workspace_id, document_id=document.id,
                    passage_id=passage.id, field=field, raw_value=raw,
                    normalized_value=normalized, unit="INR", status=local_status,
                )
            )
            ent_name = f"INR {normalized}"
            entity = db.scalar(select(Entity).where(Entity.workspace_id == document.workspace_id, Entity.type == "amount", Entity.name == ent_name))
            if not entity:
                entity = Entity(id=uid("ent"), workspace_id=document.workspace_id, type="amount", name=ent_name)
                db.add(entity)
                db.flush()
            existing = db.scalar(select(DocumentEntity).where(DocumentEntity.document_id == document.id, DocumentEntity.entity_id == entity.id, DocumentEntity.passage_id == passage.id))
            if not existing:
                db.add(DocumentEntity(document_id=document.id, entity_id=entity.id, passage_id=passage.id, mention_text=raw))

        if any(word in lower for word in FIELD_WORDS["submission_deadline"]):
            for raw, parsed in parse_dates(text, document.file_date.year if document.file_date else None):
                db.add(
                    Fact(
                        id=uid("fact"), workspace_id=document.workspace_id, document_id=document.id,
                        passage_id=passage.id, field="submission_deadline", raw_value=raw,
                        normalized_value=parsed.isoformat(), unit=None,
                        status=("approved" if document_approves_as_submitted and fact_status(text) == "stated" else ("stated" if is_reporting_document and fact_status(text) == "approved" else fact_status(text))),
                    )
                )


def _doc_text(passages: list[Passage]) -> str:
    return " ".join(p.text for p in passages)


def _tokens(text: str) -> set[str]:
    stop = {"the", "and", "for", "with", "from", "this", "that", "date", "project", "report", "total"}
    return {x for x in re.findall(r"[a-z0-9]+", text.lower()) if len(x) > 2 and x not in stop}


def _cosine_tokens(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / math.sqrt(len(a) * len(b))


_EVIDENCE_ACTION_WORDS = {
    "approval", "approved", "authorised", "authorized", "cites", "cited", "confirmed",
    "invoice", "item", "kits", "letter", "meeting", "minutes", "pilot", "proposal",
    "proposed", "receipt", "reference",
    "request", "requested", "review", "revision", "sanction", "sanctioned", "supports",
}


def _evidence_amounts(text: str) -> set[str]:
    amounts: set[str] = set()
    for match in AMOUNT_RE.finditer(text):
        groups = match.groups()
        raw = next((value for index, value in enumerate(groups) if index in {0, 2} and value), None)
        scale = next((value for index, value in enumerate(groups) if index in {1, 3} and value), None)
        if raw and (normalized := normalize_amount(raw, scale)):
            amounts.add(normalized)
    for match in re.finditer(r"(?:^|\|)\s*[A-Z]+\d+=([1-9][0-9]{2,8})(?:\s|$)", text):
        amounts.add(match.group(1))
    return amounts


def _filename_evidence_terms(filename: str) -> set[str]:
    stem = Path(filename).stem.replace("_", " ").replace("-", " ")
    generic = {"doc", "document", "file", "scan"}
    return {token for token in _tokens(stem) if token not in generic and not token.isdigit()}


def _evidence_pair_score(
    left: Passage,
    right: Passage,
    left_doc: Document,
    right_doc: Document,
) -> float:
    """Score a passage pair by shared, auditable relationship evidence."""
    left_text, right_text = left.text, right.text
    left_lower, right_lower = left_text.lower(), right_text.lower()
    left_tokens, right_tokens = _tokens(left_text), _tokens(right_text)
    shared_tokens = left_tokens & right_tokens
    shared_actions = shared_tokens & _EVIDENCE_ACTION_WORDS
    shared_amounts = _evidence_amounts(left_text) & _evidence_amounts(right_text)
    left_dates = {
        parsed for _raw, parsed in parse_dates(
            left_text, left_doc.file_date.year if left_doc.file_date else None
        )
    }
    right_dates = {
        parsed for _raw, parsed in parse_dates(
            right_text, right_doc.file_date.year if right_doc.file_date else None
        )
    }
    shared_dates = left_dates & right_dates
    shared_projects = set(PROJECT_RE.findall(left_text.upper())) & set(PROJECT_RE.findall(right_text.upper()))

    left_name = Path(left_doc.filename).stem.lower()
    right_name = Path(right_doc.filename).stem.lower()
    explicit_reference = left_name in right_lower or right_name in left_lower
    own_role_terms = (
        len(left_tokens & _filename_evidence_terms(left_doc.filename))
        + len(right_tokens & _filename_evidence_terms(right_doc.filename))
    )
    reference_language = len(
        (left_tokens | right_tokens)
        & {
            "approval", "approved", "authorised", "authorized", "cites", "cited", "confirmed",
            "proposed", "reference", "request", "requested", "review", "sanctioned",
        }
    )

    # Project id overlap is a deliberately weak fallback. Concrete shared
    # values, dates, items, and decision/reference language dominate it.
    return (
        20.0 * len(shared_amounts)
        + 8.0 * len(shared_dates)
        + 5.0 * len(shared_actions)
        + 3.0 * _cosine_tokens(left_text, right_text)
        + 2.0 * len(shared_tokens - shared_actions)
        + 3.0 * reference_language
        + 1.0 * own_role_terms
        + 7.0 * len(shared_projects)
        + (15.0 if explicit_reference else 0.0)
    )


def select_relationship_evidence(
    left_passages: list[Passage],
    right_passages: list[Passage],
    left_doc: Document,
    right_doc: Document,
) -> tuple[Passage | None, Passage | None]:
    """Return the best deterministic two-sided evidence pair."""
    if not left_passages or not right_passages:
        return None, None
    candidates = (
        (
            _evidence_pair_score(left, right, left_doc, right_doc),
            -left.ordinal,
            -right.ordinal,
            left,
            right,
        )
        for left in left_passages
        for right in right_passages
    )
    _score, _left_order, _right_order, left, right = max(candidates, key=lambda row: row[:3])
    return left, right


RELATIONSHIP_METHODS = ("keyword_entity", "semantic_tfidf", "hybrid")


def build_relationship_signals(
    docs: list[Document],
    passages_by_doc: dict[str, list[Passage]],
    entity_names_by_doc: dict[str, set[str]],
) -> dict[tuple[str, str], dict[str, float]]:
    """Build the one canonical signal set used by runtime and evaluation."""
    texts = {doc.id: _doc_text(passages_by_doc[doc.id]) for doc in docs}
    projects = {doc.id: set(PROJECT_RE.findall(texts[doc.id].upper())) for doc in docs}
    semantic_by_pair: dict[tuple[str, str], float] = {}
    if docs:
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), lowercase=True)
        matrix = vectorizer.fit_transform([texts[doc.id] or "__empty__" for doc in docs])
        similarities = (matrix @ matrix.T).toarray()
        positions = {doc.id: index for index, doc in enumerate(docs)}
        for left, right in combinations(docs, 2):
            semantic_by_pair[(left.id, right.id)] = float(similarities[positions[left.id], positions[right.id]])

    signals: dict[tuple[str, str], dict[str, float]] = {}
    for left, right in combinations(docs, 2):
        left_projects, right_projects = projects[left.id], projects[right.id]
        shared_projects = left_projects & right_projects
        left_entities = entity_names_by_doc.get(left.id, set())
        right_entities = entity_names_by_doc.get(right.id, set())
        union = left_entities | right_entities
        entity_overlap = len(left_entities & right_entities) / len(union) if union else 0.0
        if shared_projects:
            entity_overlap = 1.0
        filename_reference = (
            left.filename.lower() in texts[right.id].lower()
            or right.filename.lower() in texts[left.id].lower()
        )
        explicit = 1.0 if filename_reference else 0.65 if shared_projects else 0.0
        if not explicit and any(
            word in f"{texts[left.id]} {texts[right.id]}".lower()
            for word in ("cites", "reference", "meeting")
        ):
            explicit = 0.35
        temporal = 0.0
        if left.file_date and right.file_date:
            temporal = max(0.0, 1.0 - abs((left.file_date - right.file_date).days) / 90.0)
        signals[(left.id, right.id)] = {
            "entityOverlap": entity_overlap,
            "semanticSimilarity": semantic_by_pair.get((left.id, right.id), 0.0),
            "explicitReference": explicit,
            "temporalContext": temporal,
            "mismatch": 1.0 if left_projects and right_projects and left_projects.isdisjoint(right_projects) else 0.0,
            "oneProjectWithoutReference": 1.0
            if bool(left_projects) != bool(right_projects) and not filename_reference
            else 0.0,
        }
    return signals


def score_relationship(method: str, signal: dict[str, float], weights: dict[str, float]) -> float:
    if method not in RELATIONSHIP_METHODS:
        raise ValueError(f"Unknown relationship method: {method}")
    if method == "keyword_entity":
        # The lexical half of the offline baseline is the fitted TF-IDF similarity.
        return 0.70 * signal["entityOverlap"] + 0.30 * signal["semanticSimilarity"]
    if method == "semantic_tfidf":
        return signal["semanticSimilarity"]
    return sum(weights[name] * signal[name] for name in weights)


def _relationship_type(left: Document, right: Document, left_text: str, right_text: str) -> str:
    combined = f"{left.filename} {right.filename} {left_text} {right_text}".lower()
    left_name, right_name = left.filename.lower(), right.filename.lower()
    names = f"{left_name} {right_name}"
    if ("proposal" in left_name and any(role in right_name for role in ("final", "draft", "revision"))) or (
        "proposal" in right_name and any(role in left_name for role in ("final", "draft", "revision"))
    ):
        return "revision_of"
    if any(role in names for role in ("receipt", "invoice", "approval", "authorization")):
        return "supports"
    if (
        any(role in left_name for role in ("final", "draft"))
        and any(role in right_name for role in ("meeting", "review"))
    ) or (
        any(role in right_name for role in ("final", "draft"))
        and any(role in left_name for role in ("meeting", "review"))
    ):
        return "references"
    if ("meeting" in names and any(role in names for role in ("budget", "workbook"))):
        return "supports"
    if left_name in right_text.lower() or right_name in left_text.lower() or "cites" in combined or "reference" in combined:
        return "references"
    return "same_topic"


def _load_weights() -> tuple[dict[str, float], float]:
    path = BACKEND_DIR / "config" / "relationship_weights.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    weights = data["weights"]
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise RuntimeError("Relationship weights must sum to 1")
    return weights, float(data["threshold"])


def recompute_workspace(db: Session, workspace_id: str, method: str = "hybrid") -> None:
    previous_relationships = db.scalars(
        select(Relationship).where(Relationship.workspace_id == workspace_id)
    ).all()
    relationship_decisions = {
        tuple(sorted((row.source_doc_id, row.target_doc_id))): (row.id, row.review_status)
        for row in previous_relationships
    }
    rejected_pairs = {
        pair for pair, (_row_id, status) in relationship_decisions.items() if status == "rejected"
    }
    old = [row for row in previous_relationships if row.review_status != "rejected"]
    for row in old:
        db.delete(row)
    old_conflicts = db.scalars(select(Conflict).where(Conflict.workspace_id == workspace_id)).all()
    conflict_decisions: dict[tuple[str, tuple[str, ...]], tuple[str, str]] = {}
    for row in old_conflicts:
        fact_ids = db.scalars(
            select(ConflictFact.fact_id).where(ConflictFact.conflict_id == row.id)
        ).all()
        values = tuple(sorted(set(db.scalars(select(Fact.normalized_value).where(Fact.id.in_(fact_ids))).all())))
        conflict_decisions[(row.field, values)] = (row.id, row.review_status)
        db.delete(row)
    db.execute(delete(Event).where(Event.workspace_id == workspace_id))
    db.flush()

    docs = db.scalars(select(Document).where(Document.workspace_id == workspace_id, Document.status == "ready").order_by(Document.file_date, Document.id)).all()
    passages_by_doc = {
        doc.id: db.scalars(select(Passage).where(Passage.document_id == doc.id).order_by(Passage.ordinal)).all()
        for doc in docs
    }
    text_by_doc = {doc.id: _doc_text(passages_by_doc[doc.id]) for doc in docs}
    entity_names_by_doc = {
        doc.id: set(
            db.scalars(
                select(Entity.name)
                .join(DocumentEntity, DocumentEntity.entity_id == Entity.id)
                .where(DocumentEntity.document_id == doc.id)
            ).all()
        )
        for doc in docs
    }
    signals = build_relationship_signals(docs, passages_by_doc, entity_names_by_doc)
    weights, threshold = _load_weights()

    for left, right in combinations(docs, 2):
        pair = tuple(sorted((left.id, right.id)))
        if pair in rejected_pairs:
            continue
        signal = signals[(left.id, right.id)]
        if signal["mismatch"] or signal["oneProjectWithoutReference"]:
            continue
        score = score_relationship(method, signal, weights)
        if score < threshold:
            continue
        left_evidence, right_evidence = select_relationship_evidence(
            passages_by_doc[left.id], passages_by_doc[right.id], left, right
        )
        if not left_evidence or not right_evidence:
            continue
        previous_id, previous_status = relationship_decisions.get(pair, (uid("rel"), "pending"))
        rel = Relationship(
            id=previous_id, workspace_id=workspace_id, source_doc_id=left.id, target_doc_id=right.id,
            type=_relationship_type(left, right, text_by_doc[left.id], text_by_doc[right.id]), score=round(score, 6),
            entity_overlap=round(signal["entityOverlap"], 6),
            semantic_similarity=round(signal["semanticSimilarity"], 6),
            explicit_reference=round(signal["explicitReference"], 6),
            temporal_context=round(signal["temporalContext"], 6),
            review_status=previous_status,
        )
        db.add(rel)
        db.flush()
        db.add_all([
            RelationshipEvidence(relationship_id=rel.id, passage_id=left_evidence.id, role="source"),
            RelationshipEvidence(relationship_id=rel.id, passage_id=right_evidence.id, role="target"),
        ])
    db.flush()
    _build_conflicts(db, workspace_id, docs, conflict_decisions)
    _build_timeline(db, workspace_id, docs, passages_by_doc)


def _components(db: Session, workspace_id: str, doc_ids: list[str]) -> list[set[str]]:
    parent = {doc_id: doc_id for doc_id in doc_ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for rel in db.scalars(select(Relationship).where(Relationship.workspace_id == workspace_id, Relationship.review_status != "rejected")):
        if rel.source_doc_id in parent and rel.target_doc_id in parent:
            union(rel.source_doc_id, rel.target_doc_id)
    groups: dict[str, set[str]] = defaultdict(set)
    for doc_id in doc_ids:
        groups[find(doc_id)].add(doc_id)
    return list(groups.values())


def _explained_approved_transition(facts: list[Fact], docs: dict[str, Document]) -> bool:
    for approved in (fact for fact in facts if fact.status == "approved"):
        approved_date = docs[approved.document_id].file_date
        if not approved_date:
            continue
        earlier_different = any(
            docs[f.document_id].file_date and docs[f.document_id].file_date < approved_date
            and f.normalized_value != approved.normalized_value
            for f in facts
        )
        later_same = any(
            f.id != approved.id and docs[f.document_id].file_date and docs[f.document_id].file_date > approved_date
            and f.normalized_value == approved.normalized_value and f.status in {"stated", "approved"}
            for f in facts
        )
        if earlier_different and later_same:
            return True
    return False


def _explicitly_reaffirmed(db: Session, facts: list[Fact], docs: dict[str, Document]) -> bool:
    proposed = [fact for fact in facts if fact.status == "proposed"]
    if not proposed:
        return False
    for later in facts:
        later_date = docs[later.document_id].file_date
        if not later_date or not any(
            docs[item.document_id].file_date and docs[item.document_id].file_date < later_date
            and item.normalized_value != later.normalized_value
            for item in proposed
        ):
            continue
        passage = db.get(Passage, later.passage_id)
        text = passage.text.lower() if passage else ""
        if any(phrase in text for phrase in ("approved date remains", "confirmed deadline remains", "unchanged and confirmed")):
            return True
    return False


def _build_conflicts(
    db: Session,
    workspace_id: str,
    docs_list: list[Document],
    previous_decisions: dict[tuple[str, tuple[str, ...]], tuple[str, str]] | None = None,
) -> None:
    previous_decisions = previous_decisions or {}
    docs = {d.id: d for d in docs_list}
    for component in _components(db, workspace_id, list(docs)):
        if len(component) < 2:
            continue
        facts = db.scalars(select(Fact).where(Fact.workspace_id == workspace_id, Fact.document_id.in_(component))).all()
        by_field: dict[str, list[Fact]] = defaultdict(list)
        for fact in facts:
            if fact.field in {"project_budget", "submission_deadline"}:
                by_field[fact.field].append(fact)
        for field, candidates in by_field.items():
            values = {f.normalized_value for f in candidates}
            if len(values) < 2 or _explained_approved_transition(candidates, docs) or _explicitly_reaffirmed(db, candidates, docs):
                continue
            ordered = sorted(candidates, key=lambda f: (docs[f.document_id].file_date or date.min, f.document_id, f.id))
            details = "; ".join(
                f"{docs[f.document_id].filename} records {f.raw_value} as {f.status}" for f in ordered
            )
            previous_id, previous_status = previous_decisions.get(
                (field, tuple(sorted(values))), (uid("con"), "pending")
            )
            conflict = Conflict(
                id=previous_id, workspace_id=workspace_id, field=field,
                explanation=f"Potential inconsistency: {details}. The sources differ; DocTrace does not determine which value is correct.",
                severity="high" if field == "project_budget" else "medium", review_status=previous_status,
            )
            db.add(conflict)
            db.flush()
            for fact in ordered:
                db.add(ConflictFact(conflict_id=conflict.id, fact_id=fact.id))


def _build_timeline(db: Session, workspace_id: str, docs: list[Document], passages_by_doc: dict[str, list[Passage]]) -> None:
    seen: set[tuple[str, date]] = set()
    for doc in docs:
        default_year = doc.file_date.year if doc.file_date else None
        doc_passages = passages_by_doc[doc.id]
        if doc.file_date and doc_passages:
            representative = min(
                doc_passages,
                key=lambda p: min((abs((parsed - doc.file_date).days) for _raw, parsed in parse_dates(p.text, default_year)), default=10_000),
            )
            seen.add((representative.id, doc.file_date))
            db.add(Event(id=uid("evt"), workspace_id=workspace_id, document_id=doc.id, passage_id=representative.id, event_date=doc.file_date, file_date=doc.file_date, label=" ".join(representative.text.split())[:500]))
        for passage in doc_passages:
            for _raw, event_date in parse_dates(passage.text, default_year):
                key = (passage.id, event_date)
                if key in seen:
                    continue
                seen.add(key)
                label = " ".join(passage.text.split())[:500]
                db.add(Event(id=uid("evt"), workspace_id=workspace_id, document_id=doc.id, passage_id=passage.id, event_date=event_date, file_date=doc.file_date, label=label))


def relevant_component(db: Session, workspace_id: str, question: str) -> set[str]:
    docs = db.scalars(select(Document).where(Document.workspace_id == workspace_id, Document.status == "ready")).all()
    components = _components(db, workspace_id, [d.id for d in docs])
    project_ids = set(PROJECT_RE.findall(question.upper()))
    if project_ids:
        for component in components:
            text = " ".join(db.scalars(select(Passage.text).where(Passage.document_id.in_(component))).all())
            if project_ids & set(PROJECT_RE.findall(text.upper())):
                return component
    return max(components, key=len, default=set())

