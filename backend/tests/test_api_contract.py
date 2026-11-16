from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import settings
from app.database import SessionLocal, init_db
from app.main import app, create_workspace, health, list_documents, list_workspaces
from app.processing import validate_file
from app.schemas import WorkspaceCreate, WorkspaceOut


init_db()


def test_health_and_workspace_contract():
    assert health().model_dump(by_alias=True) == {
        "status": "ok", "similarityMode": settings.similarity_mode, "ocrMode": health().ocr_mode,
    }
    with SessionLocal() as db:
        created = create_workspace(WorkspaceCreate(name="Contract workspace"), db)
        payload = WorkspaceOut.model_validate(created).model_dump(mode="json", by_alias=True)
        assert set(payload) == {"id", "name", "createdAt"}
        assert created in list_workspaces(db)


def test_workspace_validation_and_scope():
    with pytest.raises(ValidationError):
        WorkspaceCreate(name="   ")
    with SessionLocal() as db:
        left = create_workspace(WorkspaceCreate(name="Left scope"), db)
        right = create_workspace(WorkspaceCreate(name="Right scope"), db)
        assert list_documents(left.id, db) == []
        assert list_documents(right.id, db) == []


def test_upload_validation_rejects_empty_unsupported_and_wrong_magic(tmp_path: Path):
    empty = tmp_path / "empty.pdf"; empty.write_bytes(b"")
    wrong = tmp_path / "wrong.pdf"; wrong.write_bytes(b"not pdf")
    with pytest.raises(ValueError, match="empty"):
        validate_file(empty, ".pdf", "pdf")
    with pytest.raises(ValueError, match="does not match"):
        validate_file(wrong, ".pdf", "pdf")


def test_routes_match_the_fixed_frontend_contract():
    actual = {(method, route.path) for route in app.routes for method in getattr(route, "methods", set())}
    required = {
        ("GET", "/health"), ("GET", "/workspaces"), ("POST", "/workspaces"),
        ("POST", "/workspaces/{workspace_id}/documents"),
        ("GET", "/workspaces/{workspace_id}/documents"), ("GET", "/documents/{document_id}"),
        ("GET", "/passages/{passage_id}"), ("GET", "/workspaces/{workspace_id}/passages/search"),
        ("GET", "/workspaces/{workspace_id}/graph"), ("PATCH", "/relationships/{relationship_id}"),
        ("GET", "/workspaces/{workspace_id}/conflicts"), ("PATCH", "/conflicts/{conflict_id}"),
        ("GET", "/workspaces/{workspace_id}/timeline"), ("POST", "/workspaces/{workspace_id}/ask"),
        ("GET", "/workspaces/{workspace_id}/audit"),
    }
    assert required <= actual
    assert settings.cors_origins == (
        "http://127.0.0.1:5173", "http://localhost:5173",
        "http://127.0.0.1:8080", "http://localhost:8080",
    )

