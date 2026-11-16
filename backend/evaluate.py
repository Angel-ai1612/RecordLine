"""Evaluate DocTrace against the independently generated synthetic corpus.

This module never changes relationship weights or thresholds.  It reads the
development and held-out labels only for scoring after predictions have been
made.  The held-out split is therefore not an input to model selection.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from itertools import combinations
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session


BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "tests" / "data"
TRUTH_PATH = DATA_DIR / "ground_truth.json"
REPORT_PATH = ROOT_DIR / "evaluation_report.md"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.analysis import (  # noqa: E402
    PROJECT_RE,
    RELATIONSHIP_METHODS,
    _build_conflicts,
    _build_timeline,
    _evidence_amounts,
    _relationship_type,
    analyze_document,
    build_relationship_signals,
    parse_dates,
    score_relationship,
    select_relationship_evidence,
)
from app.database import Base  # noqa: E402
from app.extraction import OCR, ExtractionResult, extract  # noqa: E402
from app.models import (  # noqa: E402
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
    Workspace,
)


METHODS = RELATIONSHIP_METHODS
EMPTY_METRIC_POLICY = "If both expected and predicted sets are empty, precision/recall are 1.0; otherwise a zero denominator is 0.0."


@dataclass(frozen=True)
class CorpusFile:
    path: Path
    filename: str
    split: str
    project: str
    format: str
    file_type: str


@dataclass
class ExtractedFile:
    spec: CorpusFile
    result: ExtractionResult
    seconds: float

    @property
    def text(self) -> str:
        return " ".join(p.text for p in self.result.passages)


def _safe(value: float) -> float:
    return round(float(value), 6)


def _ratio(correct: int, total: int) -> float:
    return _safe(correct / total) if total else 1.0


def _prf(predicted: set[Any], expected: set[Any]) -> dict[str, float | int]:
    true_positive = len(predicted & expected)
    false_positive = len(predicted - expected)
    false_negative = len(expected - predicted)
    if predicted:
        precision = true_positive / len(predicted)
    else:
        precision = 1.0 if not expected else 0.0
    if expected:
        recall = true_positive / len(expected)
    else:
        recall = 1.0 if not predicted else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": _safe(precision),
        "recall": _safe(recall),
        "f1": _safe(f1),
        "truePositive": true_positive,
        "falsePositive": false_positive,
        "falseNegative": false_negative,
        "predicted": len(predicted),
        "expected": len(expected),
    }


def _relationship_prf(
    predicted: set[tuple[str, str, str]],
    expected: set[tuple[str, str, str]],
    explicit_negatives: set[tuple[str, str]],
) -> dict[str, float | int]:
    """Score typed positives and explicit negatives; unlabelled pairs remain unknown."""
    true_positive = len(predicted & expected)
    expected_pairs = {(left, right) for left, right, _type in expected}
    false_positive = sum(
        1
        for left, right, rel_type in predicted
        if (left, right) in explicit_negatives
        or ((left, right) in expected_pairs and (left, right, rel_type) not in expected)
    )
    false_negative = len(expected - predicted)
    precision_denominator = true_positive + false_positive
    precision = true_positive / precision_denominator if precision_denominator else 0.0
    recall = true_positive / len(expected) if expected else (1.0 if not predicted else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": _safe(precision),
        "recall": _safe(recall),
        "f1": _safe(f1),
        "truePositive": true_positive,
        "falsePositive": false_positive,
        "falseNegative": false_negative,
        "predicted": len(predicted),
        "labelledPredicted": precision_denominator,
        "expected": len(expected),
        "mustNotLinkViolations": false_positive,
    }


def _load_truth() -> dict[str, Any]:
    return json.loads(TRUTH_PATH.read_text(encoding="utf-8"))


def _files(truth: dict[str, Any], split: str) -> list[CorpusFile]:
    result: list[CorpusFile] = []
    for item in truth["files"]:
        if item["set"] != split:
            continue
        fmt = item["format"]
        file_type = "image" if fmt in {"png", "jpg"} else "pdf" if fmt == "pdf-image" else fmt
        path = DATA_DIR / item["path"]
        result.append(
            CorpusFile(
                path=path,
                filename=path.name,
                split=split,
                project=item["project"],
                format=fmt,
                file_type=file_type,
            )
        )
    return sorted(result, key=lambda item: item.filename)


def _extract_split(files: list[CorpusFile]) -> list[ExtractedFile]:
    extracted: list[ExtractedFile] = []
    for spec in files:
        started = time.perf_counter()
        result = extract(spec.path, spec.file_type)
        extracted.append(ExtractedFile(spec, result, time.perf_counter() - started))
    return extracted


def _engine():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _foreign_keys(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


def _populate(session: Session, extracted: list[ExtractedFile], split: str) -> dict[str, str]:
    workspace_id = f"ws-eval-{split}"
    session.add(Workspace(id=workspace_id, name=f"Evaluation {split}"))
    doc_ids: dict[str, str] = {}
    for index, item in enumerate(extracted, start=1):
        document_id = f"doc-{split}-{index:03d}"
        doc_ids[item.spec.filename] = document_id
        document = Document(
            id=document_id,
            workspace_id=workspace_id,
            filename=item.spec.filename,
            stored_path=str(item.spec.path),
            sha256=hashlib.sha256(item.spec.path.read_bytes()).hexdigest(),
            file_type=item.spec.file_type,
            status="ready",
            file_date=item.result.file_date,
            processing_warning=item.result.warning,
            ocr_mode=OCR.mode if item.result.used_ocr else None,
        )
        session.add(document)
        session.flush()
        for ordinal, passage in enumerate(item.result.passages, start=1):
            session.add(
                Passage(
                    id=f"pas-{split}-{index:03d}-{ordinal:04d}",
                    document_id=document_id,
                    ordinal=ordinal,
                    text=passage.text,
                    page=passage.page,
                    paragraph_id=passage.paragraph_id,
                    sheet=passage.sheet,
                    cell=passage.cell,
                    ocr_confidence=passage.ocr_confidence,
                )
            )
        session.flush()
        analyze_document(session, document)
        session.flush()
    return doc_ids


def _signals(session: Session, workspace_id: str) -> tuple[list[Document], dict[str, list[Passage]], dict[tuple[str, str], dict[str, float]]]:
    documents = list(
        session.scalars(
            select(Document).where(Document.workspace_id == workspace_id).order_by(Document.filename)
        ).all()
    )
    passages = {
        doc.id: list(
            session.scalars(select(Passage).where(Passage.document_id == doc.id).order_by(Passage.ordinal)).all()
        )
        for doc in documents
    }
    entity_names = {
        doc.id: set(
            session.scalars(
                select(Entity.name)
                .join(DocumentEntity, DocumentEntity.entity_id == Entity.id)
                .where(DocumentEntity.document_id == doc.id)
            ).all()
        )
        for doc in documents
    }
    return documents, passages, build_relationship_signals(documents, passages, entity_names)


def _predict_relationships(
    session: Session,
    workspace_id: str,
    method: str,
    weights: dict[str, float],
    threshold: float,
) -> set[tuple[str, str, str]]:
    documents, passages, signals = _signals(session, workspace_id)
    by_id = {doc.id: doc for doc in documents}
    predicted: set[tuple[str, str, str]] = set()
    for index, ((left_id, right_id), signal) in enumerate(sorted(signals.items()), start=1):
        if signal["mismatch"] or signal["oneProjectWithoutReference"]:
            continue
        score = score_relationship(method, signal, weights)
        if score < threshold or not passages[left_id] or not passages[right_id]:
            continue
        left = by_id[left_id]
        right = by_id[right_id]
        left_text = " ".join(p.text for p in passages[left_id])
        right_text = " ".join(p.text for p in passages[right_id])
        left_evidence, right_evidence = select_relationship_evidence(
            passages[left_id], passages[right_id], left, right
        )
        if not left_evidence or not right_evidence:
            continue
        relationship_type = _relationship_type(left, right, left_text, right_text)
        relationship = Relationship(
            id=f"rel-{method}-{index:04d}",
            workspace_id=workspace_id,
            source_doc_id=left_id,
            target_doc_id=right_id,
            type=relationship_type,
            score=score,
            entity_overlap=signal["entityOverlap"],
            semantic_similarity=signal["semanticSimilarity"],
            explicit_reference=signal["explicitReference"],
            temporal_context=signal["temporalContext"],
            review_status="pending",
        )
        session.add(relationship)
        session.flush()
        session.add_all(
            [
                RelationshipEvidence(relationship_id=relationship.id, passage_id=left_evidence.id, role="source"),
                RelationshipEvidence(relationship_id=relationship.id, passage_id=right_evidence.id, role="target"),
            ]
        )
        source, target = sorted((left.filename, right.filename))
        predicted.add((source, target, relationship_type))
    session.flush()
    _build_conflicts(session, workspace_id, documents)
    _build_timeline(session, workspace_id, documents, passages)
    session.flush()
    return predicted


def _expected_relationships(truth: dict[str, Any], split: str) -> set[tuple[str, str, str]]:
    return {
        (*sorted((item["source"], item["target"])), item["type"])
        for item in truth["trueRelationships"]
        if item["set"] == split
    }


def _must_not_link(truth: dict[str, Any], split: str) -> set[tuple[str, str]]:
    return {
        tuple(sorted((item["source"], item["target"])))
        for item in truth["mustNotLink"]
        if item["set"] == split
    }


def _conflict_keys(
    session: Session,
    workspace_id: str,
    project_by_file: dict[str, str],
) -> set[tuple[str, str, tuple[str, ...]]]:
    result: set[tuple[str, str, tuple[str, ...]]] = set()
    documents = {doc.id: doc for doc in session.scalars(select(Document).where(Document.workspace_id == workspace_id))}
    for conflict in session.scalars(select(Conflict).where(Conflict.workspace_id == workspace_id)):
        fact_ids = list(
            session.scalars(select(ConflictFact.fact_id).where(ConflictFact.conflict_id == conflict.id)).all()
        )
        facts = list(session.scalars(select(Fact).where(Fact.id.in_(fact_ids))).all()) if fact_ids else []
        projects = {project_by_file.get(documents[fact.document_id].filename, "unknown") for fact in facts}
        project = next(iter(projects)) if len(projects) == 1 else "mixed"
        values = tuple(sorted({fact.normalized_value for fact in facts}))
        result.add((project, conflict.field, values))
    return result


def _expected_conflict_keys(truth: dict[str, Any], split: str) -> set[tuple[str, str, tuple[str, ...]]]:
    project_splits = {name: value["set"] for name, value in truth["projects"].items()}
    return {
        (item["project"], item["canonicalField"], tuple(sorted(item["normalizedValues"])))
        for item in truth["expectedConflicts"]
        if project_splits[item["project"]] == split
    }


def _label_tokens(value: str) -> set[str]:
    import re

    stop = {"the", "and", "for", "with", "same", "project", "held", "out", "final"}
    canonical = {
        "approval": "approve", "approved": "approve", "approves": "approve",
        "cited": "cite", "cites": "cite", "proposal": "propose", "proposed": "propose",
        "requested": "request", "sanctioned": "sanction", "used": "use", "uses": "use",
        "values": "value",
    }
    return {
        canonical.get(token, token)
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 2 and token not in stop
    }


def _evidence_accuracy(
    session: Session, workspace_id: str, truth: dict[str, Any], split: str
) -> dict[str, float | int]:
    correct = 0
    total = 0
    passages = {p.id: p for p in session.scalars(select(Passage)).all()}
    documents = {
        doc.id: doc.filename
        for doc in session.scalars(select(Document).where(Document.workspace_id == workspace_id))
    }
    expected_relationships = {
        tuple(sorted((item["source"], item["target"]))): item
        for item in truth["trueRelationships"]
        if item["set"] == split
    }
    for relationship in session.scalars(select(Relationship).where(Relationship.workspace_id == workspace_id)):
        ids = list(
            session.scalars(
                select(RelationshipEvidence.passage_id).where(RelationshipEvidence.relationship_id == relationship.id)
            ).all()
        )
        pair = tuple(sorted((documents[relationship.source_doc_id], documents[relationship.target_doc_id])))
        expected = expected_relationships.get(pair)
        if not expected:
            continue
        total += 1
        evidence_rows = [passages.get(item) for item in ids]
        evidence_text = " ".join(row.text.lower() for row in evidence_rows if row)
        reason_tokens = _label_tokens(expected["reason"]) if expected else set()
        evidence_by_document = {
            document_id: " ".join(
                row.text for row in evidence_rows if row and row.document_id == document_id
            )
            for document_id in (relationship.source_doc_id, relationship.target_doc_id)
        }
        shared_project_ids = set.intersection(
            *(set(PROJECT_RE.findall(text.upper())) for text in evidence_by_document.values())
        )
        shared_amounts = set.intersection(
            *(_evidence_amounts(text) for text in evidence_by_document.values())
        )
        reason_lower = expected["reason"].lower()
        reason_is_supported = bool(reason_tokens & _label_tokens(evidence_text)) or (
            "project id" in reason_lower and bool(shared_project_ids)
        ) or (
            any(word in reason_lower for word in ("amount", "value", "unchanged"))
            and bool(shared_amounts)
        )
        if (
            relationship.type == expected["type"]
            and {row.document_id for row in evidence_rows if row}
            == {relationship.source_doc_id, relationship.target_doc_id}
            and reason_is_supported
        ):
            correct += 1
    expected_facts = {
        (item["document"], item["canonicalField"], item["normalizedValue"], item["status"])
        for item in truth["expectedFacts"]
        if item["set"] == split
    }
    for conflict in session.scalars(select(Conflict).where(Conflict.workspace_id == workspace_id)):
        total += 1
        fact_ids = list(
            session.scalars(select(ConflictFact.fact_id).where(ConflictFact.conflict_id == conflict.id)).all()
        )
        facts = list(session.scalars(select(Fact).where(Fact.id.in_(fact_ids))).all()) if fact_ids else []
        if len(facts) >= 2 and all(
            passages.get(fact.passage_id)
            and passages[fact.passage_id].document_id == fact.document_id
            and (documents[fact.document_id], fact.field, fact.normalized_value, fact.status) in expected_facts
            for fact in facts
        ):
            correct += 1
    return {"accuracy": _ratio(correct, total), "correct": correct, "total": total}


def _timeline_accuracy(
    session: Session,
    workspace_id: str,
    truth: dict[str, Any],
    split: str,
) -> dict[str, float | int]:
    docs = {doc.id: doc.filename for doc in session.scalars(select(Document).where(Document.workspace_id == workspace_id))}
    passages = {p.id: p for p in session.scalars(select(Passage)).all()}
    events_by_file: dict[str, list[Event]] = defaultdict(list)
    for row in session.scalars(select(Event).where(Event.workspace_id == workspace_id)):
        events_by_file[docs[row.document_id]].append(row)
    correct = 0
    expected = [item for item in truth["expectedTimeline"] if item["set"] == split]
    for item in expected:
        if any(
            row.event_date.isoformat() == item["eventDate"]
            and row.file_date
            and row.file_date.isoformat() == item["fileDate"]
            and passages.get(row.passage_id)
            and date.fromisoformat(item["eventDate"])
            in {parsed for _raw, parsed in parse_dates(passages[row.passage_id].text, row.file_date.year)}
            for row in events_by_file.get(item["document"], [])
        ):
            correct += 1
    return {"accuracy": _ratio(correct, len(expected)), "correct": correct, "total": len(expected)}


def _fact_accuracy(
    session: Session,
    workspace_id: str,
    truth: dict[str, Any],
    split: str,
) -> dict[str, Any]:
    documents = {doc.id: doc.filename for doc in session.scalars(select(Document).where(Document.workspace_id == workspace_id))}
    actual = {
        (documents[fact.document_id], fact.field, fact.normalized_value, fact.status)
        for fact in session.scalars(select(Fact).where(Fact.workspace_id == workspace_id))
    }
    expected_items = [item for item in truth["expectedFacts"] if item["set"] == split]
    correct = sum(
        (
            item["document"],
            item["canonicalField"],
            item["normalizedValue"],
            item["status"],
        )
        in actual
        for item in expected_items
    )
    return {"accuracy": _ratio(correct, len(expected_items)), "correct": correct, "total": len(expected_items)}


def _ocr_accuracy(session: Session, workspace_id: str, truth: dict[str, Any], split: str) -> dict[str, Any]:
    if split != "dev":
        return {"accuracy": 1.0, "correct": 0, "total": 0, "mode": OCR.mode}
    documents = {doc.id: doc.filename for doc in session.scalars(select(Document).where(Document.workspace_id == workspace_id))}
    facts = list(session.scalars(select(Fact).where(Fact.workspace_id == workspace_id)).all())
    expected_pairs: set[tuple[str, str]] = set()
    for item in truth["ocrExpectedValues"]:
        expected_pairs.update((filename, item["normalizedValue"]) for filename in item["documents"])
    actual_pairs = {(documents[fact.document_id], fact.normalized_value) for fact in facts}
    correct = len(expected_pairs & actual_pairs)
    return {"accuracy": _ratio(correct, len(expected_pairs)), "correct": correct, "total": len(expected_pairs), "mode": OCR.mode}


def _per_format(
    extracted: list[ExtractedFile],
    session: Session,
    workspace_id: str,
    truth: dict[str, Any],
    split: str,
) -> dict[str, Any]:
    docs = {doc.id: doc.filename for doc in session.scalars(select(Document).where(Document.workspace_id == workspace_id))}
    actual = {
        (docs[fact.document_id], fact.field, fact.normalized_value, fact.status)
        for fact in session.scalars(select(Fact).where(Fact.workspace_id == workspace_id))
    }
    format_by_file = {item.spec.filename: item.spec.format for item in extracted}
    expected_by_format: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in truth["expectedFacts"]:
        if item["set"] == split:
            expected_by_format[format_by_file[item["document"]]].append(item)
    output: dict[str, Any] = {}
    for fmt in sorted({item.spec.format for item in extracted}):
        items = [item for item in extracted if item.spec.format == fmt]
        expected = expected_by_format.get(fmt, [])
        correct = sum(
            (item["document"], item["canonicalField"], item["normalizedValue"], item["status"]) in actual
            for item in expected
        )
        output[fmt] = {
            "files": len(items),
            "withPassages": sum(bool(item.result.passages) for item in items),
            "expectedFacts": len(expected),
            "correctFacts": correct,
            "factAccuracy": _ratio(correct, len(expected)),
            "processingSeconds": _safe(sum(item.seconds for item in items)),
        }
    return output


def _evaluate_method(
    truth: dict[str, Any],
    extracted: list[ExtractedFile],
    split: str,
    method: str,
    weights: dict[str, float],
    threshold: float,
) -> dict[str, Any]:
    started = time.perf_counter()
    engine = _engine()
    try:
        with Session(engine) as session:
            doc_ids = _populate(session, extracted, split)
            workspace_id = f"ws-eval-{split}"
            predicted_relationships = _predict_relationships(
                session, workspace_id, method, weights, threshold
            )
            session.flush()
            project_by_file = {item.spec.filename: item.spec.project for item in extracted}
            relationship_metrics = _relationship_prf(
                predicted_relationships,
                _expected_relationships(truth, split),
                _must_not_link(truth, split),
            )
            metrics = {
                "relationship": relationship_metrics,
                "conflict": _prf(
                    _conflict_keys(session, workspace_id, project_by_file),
                    _expected_conflict_keys(truth, split),
                ),
                "evidence": _evidence_accuracy(session, workspace_id, truth, split),
                "timeline": _timeline_accuracy(session, workspace_id, truth, split),
                "ocrAmount": _ocr_accuracy(session, workspace_id, truth, split),
                "fact": _fact_accuracy(session, workspace_id, truth, split),
                "perFormat": _per_format(extracted, session, workspace_id, truth, split),
                "processingSeconds": _safe(
                    time.perf_counter() - started + sum(item.seconds for item in extracted)
                ),
                "documents": len(doc_ids),
            }
            session.rollback()
            return metrics
    finally:
        engine.dispose()


def evaluate() -> dict[str, Any]:
    truth = _load_truth()
    config = json.loads((BACKEND_DIR / "config" / "relationship_weights.json").read_text(encoding="utf-8"))
    weights = config["weights"]
    threshold = float(config["threshold"])
    if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9):
        raise RuntimeError("Relationship weights must sum to 1")
    output: dict[str, Any] = {
        "dataset": truth["description"],
        "groundTruth": str(TRUTH_PATH.relative_to(ROOT_DIR)).replace("\\", "/"),
        "semanticMode": "tfidf",
        "ocrMode": OCR.mode,
        "threshold": threshold,
        "weights": weights,
        "emptyMetricPolicy": EMPTY_METRIC_POLICY,
        "heldoutUsedForTuning": False,
        "splits": {},
    }
    for split in ("dev", "heldout"):
        extracted = _extract_split(_files(truth, split))
        output["splits"][split] = {
            method: _evaluate_method(truth, extracted, split, method, weights, threshold)
            for method in METHODS
        }
    return output


def _pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def _measured_pct(data: dict[str, Any]) -> str:
    total = data.get("total", data.get("totalPairs", 0))
    return _pct(data["accuracy"]) if total else "N/A"


def _render_report(result: dict[str, Any]) -> str:
    lines = [
        "# DocTrace Synthetic Evaluation",
        "",
        "> These results come from a small, generated synthetic dataset. They are regression evidence only and are not general accuracy claims.",
        "",
        "## Method and scoring policy",
        "",
        f"- Ground truth: `{result['groundTruth']}`, generated independently from scenario definitions.",
        "- `keyword_entity`: 70% extracted-entity overlap and 30% TF-IDF lexical similarity.",
        "- `semantic_tfidf`: TF-IDF unigram/bigram cosine similarity only.",
        "- `hybrid`: configured entity, TF-IDF, explicit-reference and temporal weights.",
        f"- Relationship threshold: `{result['threshold']}`. Held-out labels were never used for tuning: `{str(not result['heldoutUsedForTuning']).lower()}`.",
        f"- OCR mode during this run: `{result['ocrMode']}`.",
        f"- Zero-denominator policy: {result['emptyMetricPolicy']}",
        "- Relationship metrics are typed and calculated over annotated positives plus explicit must-not-link negatives. Unlabelled predicted pairs remain unknown, so relationship precision is labelled precision, not exhaustive-corpus precision. Conflict metrics use project, canonical field and normalized value set. Evidence accuracy requires expected relationship type, reason-relevant passages from both documents, and independently labelled conflict facts. Timeline accuracy requires an expected event with exact eventDate and fileDate plus label-relevant source text.",
        "",
    ]
    for split in ("dev", "heldout"):
        lines.extend(
            [
                f"## {split.capitalize()} results",
                "",
                "| Method | Relationship labelled P / R / F1 | Must-not violations | Conflict P / R | Evidence | Timeline | OCR amount | Fact status/value | Seconds |",
                "| --- | --- | ---: | --- | --- | --- | --- | --- | ---: |",
            ]
        )
        for method in METHODS:
            data = result["splits"][split][method]
            rel = data["relationship"]
            conflict = data["conflict"]
            lines.append(
                "| "
                + " | ".join(
                    [
                        method,
                        f"{_pct(rel['precision'])} / {_pct(rel['recall'])} / {_pct(rel['f1'])}",
                        str(rel["mustNotLinkViolations"]),
                        f"{_pct(conflict['precision'])} / {_pct(conflict['recall'])}",
                        _measured_pct(data["evidence"]),
                        _measured_pct(data["timeline"]),
                        _measured_pct(data["ocrAmount"]),
                        _measured_pct(data["fact"]),
                        f"{data['processingSeconds']:.3f}",
                    ]
                )
                + " |"
            )
        lines.extend(["", "### Per-format extraction and fact results", ""])
        representative = result["splits"][split]["hybrid"]["perFormat"]
        lines.extend(
            [
                "| Format | Files | Files with passages | Expected facts | Correct facts | Fact accuracy | Extraction seconds |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for fmt, data in representative.items():
            lines.append(
                f"| {fmt} | {data['files']} | {data['withPassages']} | {data['expectedFacts']} | "
                f"{data['correctFacts']} | {_pct(data['factAccuracy'])} | {data['processingSeconds']:.3f} |"
            )
        lines.append("")
    ocr_limitation = (
        "- RapidOCR was active for this run; OCR scores cover only the generated noisy receipt variants."
        if result["ocrMode"] == "rapidocr"
        else "- RapidOCR was unavailable; image and image-only PDF amount accuracy measures the graceful-fallback path, not OCR model quality."
    )
    lines.extend([
        "## Limitations observed in this run", "", ocr_limitation,
        "- Processing time is local wall-clock time on one machine and is not a capacity benchmark.",
        "- The synthetic corpus is intentionally tiny. A score of 100% on any metric is not evidence of real-world accuracy.", "",
    ])
    return "\n".join(lines)


def main() -> int:
    result = evaluate()
    REPORT_PATH.write_text(_render_report(result), encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    print(f"Wrote {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
