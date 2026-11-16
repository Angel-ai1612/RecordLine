from __future__ import annotations

import json
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

import app.extraction as extraction_module
import app.processing as processing_module
from app.analysis import recompute_workspace
from app.database import SessionLocal, init_db
from app.main import app
from app.models import ConflictFact, Document, Fact


BACKEND = Path(__file__).resolve().parents[1]
DATA = Path(__file__).parent / "data"
TRUTH = json.loads((DATA / "ground_truth.json").read_text(encoding="utf-8"))

DOCUMENT_KEYS = {"id", "workspaceId", "filename", "fileType", "status", "uploadedAt", "fileDate"}
PASSAGE_KEYS = {"id", "documentId", "text", "locator", "ocrConfidence", "highlight"}
RELATIONSHIP_KEYS = {
    "id", "sourceDocId", "targetDocId", "type", "score", "signals",
    "evidencePassageIds", "reviewStatus",
}
FACT_KEYS = {
    "id", "documentId", "passageId", "field", "rawValue", "normalizedValue", "unit", "status",
}


@contextmanager
def _asgi_client():
    init_db()
    with TestClient(app) as client:
        yield client


def _create_workspace(client: TestClient, prefix: str) -> str:
    response = client.post("/workspaces", json={"name": f"{prefix}-{uuid.uuid4().hex}"})
    assert response.status_code == 201, response.text
    assert set(response.json()) == {"id", "name", "createdAt"}
    return response.json()["id"]


def _wait_terminal(client: TestClient, document_id: str) -> tuple[dict, set[str]]:
    deadline = time.monotonic() + 60
    observed: set[str] = set()
    while time.monotonic() < deadline:
        response = client.get(f"/documents/{document_id}")
        assert response.status_code == 200, response.text
        payload = response.json()
        observed.add(payload["status"])
        if payload["status"] in {"ready", "failed"}:
            return payload, observed
        time.sleep(0.05)
    raise AssertionError(f"document {document_id} did not reach a terminal state")


def _upload_dev_corpus(client: TestClient) -> tuple[str, dict[str, dict]]:
    workspace_id = _create_workspace(client, "acceptance")
    uploaded: dict[str, dict] = {}
    for item in (row for row in TRUTH["files"] if row["set"] == "dev"):
        path = DATA / item["path"]
        with path.open("rb") as handle:
            response = client.post(
                f"/workspaces/{workspace_id}/documents",
                files={"file": (path.name, handle, "application/octet-stream")},
            )
        assert response.status_code == 202, (path.name, response.text)
        queued = response.json()
        assert set(queued) == DOCUMENT_KEYS
        assert queued["status"] == "queued"
        terminal, observed = _wait_terminal(client, queued["id"])
        assert terminal["status"] == "ready", (path.name, terminal)
        assert "ready" in observed
        uploaded[path.name] = terminal

    final = client.get(f"/workspaces/{workspace_id}/documents")
    assert final.status_code == 200
    assert len(final.json()) == len(uploaded)
    assert all(set(row) == DOCUMENT_KEYS and row["status"] == "ready" for row in final.json())
    return workspace_id, uploaded


def _pair(row: dict, filenames: dict[str, str]) -> tuple[str, str]:
    return tuple(sorted((filenames[row["sourceDocId"]], filenames[row["targetDocId"]])))


def test_full_generated_corpus_matches_acceptance_and_ui_sequence(monkeypatch):
    # Acceptance validates extraction and analysis results; subprocess lifecycle is
    # covered separately so Windows spawn cannot recursively bootstrap pytest.
    monkeypatch.setattr(
        processing_module,
        "extract_isolated",
        lambda path, file_type: extraction_module.extract(path, file_type),
    )
    with _asgi_client() as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert set(health.json()) == {"status", "similarityMode", "ocrMode"}
        assert health.json()["status"] == "ok"

        workspace_id, uploaded = _upload_dev_corpus(client)
        filenames_by_id = {row["id"]: name for name, row in uploaded.items()}

        graph_response = client.get(f"/workspaces/{workspace_id}/graph")
        assert graph_response.status_code == 200
        graph = graph_response.json()
        assert set(graph) == {"documents", "entities", "relationships"}
        assert all(set(row) == DOCUMENT_KEYS for row in graph["documents"])
        assert all(set(row) == {"id", "type", "name", "documentIds"} for row in graph["entities"])
        assert all(set(row) == RELATIONSHIP_KEYS for row in graph["relationships"])
        assert graph["documents"] == sorted(graph["documents"], key=lambda row: (row["uploadedAt"], row["id"]))
        assert graph["entities"] == sorted(graph["entities"], key=lambda row: (row["type"], row["name"]))
        assert graph["relationships"] == sorted(
            graph["relationships"], key=lambda row: (-row["score"], row["id"])
        )
        actual_edges = {_pair(row, filenames_by_id): row for row in graph["relationships"]}
        relationship_errors = []
        for expected in (item for item in TRUTH["trueRelationships"] if item["set"] == "dev"):
            pair = tuple(sorted((expected["source"], expected["target"])))
            if pair not in actual_edges:
                relationship_errors.append(f"missing relationship {pair}: {expected['reason']}")
            elif actual_edges[pair]["type"] != expected["type"]:
                relationship_errors.append(
                    f"wrong type for {pair}: expected {expected['type']}, "
                    f"got {actual_edges[pair]['type']}"
                )
        for forbidden in (item for item in TRUTH["mustNotLink"] if item["set"] == "dev"):
            pair = tuple(sorted((forbidden["source"], forbidden["target"])))
            if pair in actual_edges:
                relationship_errors.append(f"forbidden relationship {pair}: {forbidden['trap']}")
        for relationship in graph["relationships"]:
            assert len(relationship["evidencePassageIds"]) >= 2
            evidence_doc_ids = set()
            for passage_id in relationship["evidencePassageIds"]:
                passage_response = client.get(f"/passages/{passage_id}")
                assert passage_response.status_code == 200
                passage = passage_response.json()
                assert set(passage) == PASSAGE_KEYS
                evidence_doc_ids.add(passage["documentId"])
            assert evidence_doc_ids == {relationship["sourceDocId"], relationship["targetDocId"]}

        conflict_response = client.get(f"/workspaces/{workspace_id}/conflicts")
        assert conflict_response.status_code == 200
        conflicts = conflict_response.json()
        assert len(conflicts) == 2
        assert {row["field"] for row in conflicts} == {"project_budget", "submission_deadline"}
        assert conflicts == sorted(conflicts, key=lambda row: (row["field"], row["id"]))
        for conflict in conflicts:
            assert set(conflict) == {
                "id", "field", "factIds", "explanation", "severity", "reviewStatus", "facts",
            }
            assert conflict["reviewStatus"] == "pending"
            assert "does not determine which value is correct" in conflict["explanation"]
            assert all(set(fact) == FACT_KEYS for fact in conflict["facts"])
            for fact in conflict["facts"]:
                passage = client.get(f"/passages/{fact['passageId']}").json()
                assert passage["documentId"] == fact["documentId"]
                assert filenames_by_id[fact["documentId"]].startswith("medsaathi_")
        values = {row["field"]: {fact["normalizedValue"] for fact in row["facts"]} for row in conflicts}
        assert values == {
            "project_budget": {"50000", "65000"},
            "submission_deadline": {"2026-11-20", "2026-11-25"},
        }

        with SessionLocal() as db:
            docs = {
                row.id: row.filename
                for row in db.scalars(select(Document).where(Document.workspace_id == workspace_id)).all()
            }
            facts = {
                (docs[row.document_id], row.field, row.normalized_value, row.status)
                for row in db.scalars(select(Fact).where(Fact.workspace_id == workspace_id)).all()
            }
            for expected in (item for item in TRUTH["expectedFacts"] if item["set"] == "dev"):
                assert (
                    expected["document"], expected["canonicalField"],
                    expected["normalizedValue"], expected["status"],
                ) in facts, expected
            conflict_fact_ids = set(
                db.scalars(
                    select(ConflictFact.fact_id).join(Fact, Fact.id == ConflictFact.fact_id)
                    .where(Fact.workspace_id == workspace_id)
                ).all()
            )
            conflict_filenames = {
                docs[fact.document_id]
                for fact in db.scalars(select(Fact).where(Fact.id.in_(conflict_fact_ids))).all()
            }
            assert not any(name.startswith(("nanogrid_", "waterwise_", "agrisense_")) for name in conflict_filenames)

        timeline_response = client.get(f"/workspaces/{workspace_id}/timeline")
        assert timeline_response.status_code == 200
        timeline = timeline_response.json()
        assert all(set(row) == {"id", "documentId", "passageId", "eventDate", "fileDate", "label"} for row in timeline)
        assert timeline == sorted(
            timeline, key=lambda row: (row["eventDate"], row["documentId"], row["id"])
        )
        timeline_errors: set[str] = set()
        for event in timeline:
            passage = client.get(f"/passages/{event['passageId']}").json()
            assert passage["documentId"] == event["documentId"]
            filename = filenames_by_id[event["documentId"]]
            expected_file_date = next(item["fileDate"] for item in TRUTH["files"] if Path(item["path"]).name == filename)
            if event["fileDate"] != expected_file_date:
                timeline_errors.add(
                    f"wrong file date for {filename}: expected {expected_file_date}, got {event['fileDate']}"
                )
        actual_timeline = {
            (filenames_by_id[row["documentId"]], row["eventDate"], row["fileDate"])
            for row in timeline
        }
        expected_timeline = {
            (row["document"], row["eventDate"], row["fileDate"])
            for row in TRUTH["expectedTimeline"] if row["set"] == "dev"
        }
        for missing in sorted(expected_timeline - actual_timeline):
            timeline_errors.add(f"missing expected timeline event {missing}")

        search = client.get(f"/workspaces/{workspace_id}/passages/search", params={"q": "MS-2026-01 budget"})
        assert search.status_code == 200 and search.json()
        assert all(set(hit) == {"passage", "score"} and set(hit["passage"]) == PASSAGE_KEYS for hit in search.json())

        answer_response = client.post(
            f"/workspaces/{workspace_id}/ask",
            json={"question": "What budget was discussed for project MS-2026-01?"},
        )
        assert answer_response.status_code == 200
        answer = answer_response.json()
        assert set(answer) == {"text", "citations", "ambiguityNote"}
        assert "50000" in answer["text"].replace(",", "")
        assert "65000" in answer["text"].replace(",", "")
        assert answer["ambiguityNote"]
        assert len(answer["citations"]) >= 4
        for citation in answer["citations"]:
            assert set(citation) == {"passageId", "documentId"}
            passage = client.get(f"/passages/{citation['passageId']}").json()
            assert passage["documentId"] == citation["documentId"]

        relationship = graph["relationships"][0]
        reviewed_relationship = client.patch(
            f"/relationships/{relationship['id']}", json={"reviewStatus": "confirmed"}
        )
        assert reviewed_relationship.status_code == 200
        assert reviewed_relationship.json()["reviewStatus"] == "confirmed"
        reviewed_conflict = client.patch(
            f"/conflicts/{conflicts[0]['id']}", json={"reviewStatus": "rejected"}
        )
        assert reviewed_conflict.status_code == 200
        assert reviewed_conflict.json()["reviewStatus"] == "rejected"

        # A later document normally causes this recomputation. Reviews and their
        # audit targets must remain stable across that lifecycle transition.
        with SessionLocal() as db:
            recompute_workspace(db, workspace_id)
            db.commit()
        refreshed_graph = client.get(f"/workspaces/{workspace_id}/graph").json()
        refreshed_conflicts = client.get(f"/workspaces/{workspace_id}/conflicts").json()
        assert next(row for row in refreshed_graph["relationships"] if row["id"] == relationship["id"])[
            "reviewStatus"
        ] == "confirmed"
        assert next(row for row in refreshed_conflicts if row["id"] == conflicts[0]["id"])[
            "reviewStatus"
        ] == "rejected"
        audit_response = client.get(f"/workspaces/{workspace_id}/audit")
        assert audit_response.status_code == 200
        audit = audit_response.json()
        assert len(audit) == 2
        assert {row["targetType"] for row in audit} == {"relationship", "conflict"}
        expected_audit_order = sorted(audit, key=lambda row: row["id"])
        expected_audit_order.sort(key=lambda row: row["createdAt"], reverse=True)
        assert audit == expected_audit_order
        assert all(set(row) == {
            "id", "workspaceId", "targetType", "targetId", "action", "actor", "note", "createdAt",
        } for row in audit)
        acceptance_errors = relationship_errors + sorted(timeline_errors)
        assert not acceptance_errors, "\n".join(acceptance_errors)
