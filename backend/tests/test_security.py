from __future__ import annotations

import hashlib
import io
import struct
import uuid
import zipfile
from pathlib import Path

import pytest
from sqlalchemy import select

import app.extraction as extraction_module
import app.processing as processing_module
from app.config import settings
from app.database import SessionLocal
from app.extraction import OcrEngine
from app.models import Document, Passage, Workspace
from app.processing import process_document
from test_acceptance import _asgi_client, _wait_terminal


DATA = Path(__file__).parent / "data"
ROBUST = DATA / "robustness"


def _workspace(client, label: str) -> str:
    response = client.post("/workspaces", json={"name": f"{label}-{uuid.uuid4().hex}"})
    assert response.status_code == 201
    return response.json()["id"]


def _post_file(client, workspace_id: str, path: Path, *, name: str | None = None):
    with path.open("rb") as handle:
        return client.post(
            f"/workspaces/{workspace_id}/documents",
            files={"file": (name or path.name, handle, "application/octet-stream")},
        )


def _office_fixture(path: Path, mode: str) -> None:
    content_types = (
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        + ('<Override ContentType="application/vnd.ms-word.document.macroEnabled.main+xml"/>'
           if mode == "macro" else "")
        + "</Types>"
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("word/document.xml", "<document/>")
        if mode == "external":
            archive.writestr(
                "word/_rels/document.xml.rels",
                '<Relationships><Relationship TargetMode="External" '
                'Target="https://example.invalid/"/></Relationships>',
            )
    if mode == "encrypted":
        payload = bytearray(path.read_bytes())
        cursor = 0
        while (cursor := payload.find(b"PK\x03\x04", cursor)) >= 0:
            flags = struct.unpack_from("<H", payload, cursor + 6)[0]
            struct.pack_into("<H", payload, cursor + 6, flags | 0x1)
            cursor += 4
        cursor = 0
        while (cursor := payload.find(b"PK\x01\x02", cursor)) >= 0:
            flags = struct.unpack_from("<H", payload, cursor + 8)[0]
            struct.pack_into("<H", payload, cursor + 8, flags | 0x1)
            cursor += 4
        path.write_bytes(payload)


def test_upload_validation_limits_sanitization_and_error_hygiene(monkeypatch):
    monkeypatch.setattr(
        processing_module,
        "extract_isolated",
        lambda path, file_type: extraction_module.extract(path, file_type),
    )
    with _asgi_client() as client:
        workspace_id = _workspace(client, "upload-security")
        for filename in ("empty.pdf", "corrupted.pdf", "wrong_extension.pdf"):
            response = _post_file(client, workspace_id, ROBUST / filename)
            assert response.status_code == 415
            assert set(response.json()) == {"detail"}
            assert "traceback" not in response.text.lower()
        unsupported = _post_file(client, workspace_id, ROBUST / "unsupported.txt")
        assert unsupported.status_code == 415
        assert unsupported.json() == {"detail": "Unsupported file type"}
        oversized = io.BytesIO(b"%PDF-1.7\n" + b"0" * settings.max_upload_bytes)
        response = client.post(
            f"/workspaces/{workspace_id}/documents",
            files={"file": ("oversized.pdf", oversized, "application/pdf")},
        )
        assert response.status_code == 413
        assert "25 MB" in response.json()["detail"]

        response = _post_file(client, workspace_id, DATA / "medsaathi_proposal.pdf", name="../../folder/evil.pdf")
        assert response.status_code == 202
        payload = response.json()
        assert payload["filename"] == "evil.pdf"
        assert _wait_terminal(client, payload["id"])[0]["status"] == "ready"
        with SessionLocal() as db:
            document = db.get(Document, payload["id"])
            assert document is not None
            stored = Path(document.stored_path).resolve()
            assert stored.parent == settings.files_dir.resolve()
            assert stored.name.startswith("doc-") and stored.suffix == ".pdf"


def test_cors_and_security_headers_allow_only_configured_vite_origins():
    with _asgi_client() as client:
        for origin in settings.cors_origins:
            allowed = client.options(
                "/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET"}
            )
            assert allowed.status_code == 200
            assert allowed.headers["access-control-allow-origin"] == origin
        blocked = client.options(
            "/health",
            headers={"Origin": "https://attacker.example", "Access-Control-Request-Method": "GET"},
        )
        assert blocked.status_code == 400
        assert "access-control-allow-origin" not in blocked.headers
        response = client.get("/health")
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["cache-control"] == "no-store"


def test_workspace_collections_search_and_analysis_are_isolated(monkeypatch):
    monkeypatch.setattr(
        processing_module,
        "extract_isolated",
        lambda path, file_type: extraction_module.extract(path, file_type),
    )
    with _asgi_client() as client:
        left = _workspace(client, "scope-left")
        right = _workspace(client, "scope-right")
        left_upload = _post_file(client, left, DATA / "medsaathi_proposal.pdf").json()
        right_upload = _post_file(client, right, DATA / "agrisense_brief.pdf").json()
        assert _wait_terminal(client, left_upload["id"])[0]["status"] == "ready"
        assert _wait_terminal(client, right_upload["id"])[0]["status"] == "ready"
        assert {row["id"] for row in client.get(f"/workspaces/{left}/documents").json()} == {left_upload["id"]}
        assert {row["id"] for row in client.get(f"/workspaces/{right}/documents").json()} == {right_upload["id"]}
        assert {row["id"] for row in client.get(f"/workspaces/{left}/graph").json()["documents"]} == {left_upload["id"]}
        assert {row["id"] for row in client.get(f"/workspaces/{right}/graph").json()["documents"]} == {right_upload["id"]}
        left_search = client.get(f"/workspaces/{left}/passages/search", params={"q": "MS-2026-01"}).json()
        right_search = client.get(f"/workspaces/{right}/passages/search", params={"q": "MS-2026-01"}).json()
        assert left_search and right_search
        assert all(hit["passage"]["documentId"] == left_upload["id"] for hit in left_search)
        assert all(hit["passage"]["documentId"] == right_upload["id"] for hit in right_search)
        assert client.get(f"/workspaces/{left}/conflicts").json() == []
        assert client.get(f"/workspaces/{right}/conflicts").json() == []
        assert all(row["documentId"] == left_upload["id"] for row in client.get(f"/workspaces/{left}/timeline").json())
        assert all(row["documentId"] == right_upload["id"] for row in client.get(f"/workspaces/{right}/timeline").json())


def test_ocr_unavailable_is_document_local_and_records_a_clear_warning(monkeypatch):
    unavailable = OcrEngine()
    monkeypatch.setattr(extraction_module, "OCR", unavailable)
    monkeypatch.setattr(processing_module, "OCR", unavailable)
    monkeypatch.setattr(
        processing_module,
        "extract_isolated",
        lambda path, file_type: extraction_module.extract(path, file_type),
    )
    workspace_id = f"ws-ocr-fallback-{uuid.uuid4().hex}"
    document_id = f"doc-ocr-fallback-{uuid.uuid4().hex}"
    source = DATA / "medsaathi_receipt.png"
    with SessionLocal() as db:
        db.add(Workspace(id=workspace_id, name=f"OCR fallback {uuid.uuid4().hex}"))
        db.add(
            Document(
                id=document_id,
                workspace_id=workspace_id,
                filename=source.name,
                stored_path=str(source),
                sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                file_type="image",
                status="queued",
            )
        )
        db.commit()
    process_document(document_id)
    with SessionLocal() as db:
        document = db.get(Document, document_id)
        assert document is not None and document.status == "ready"
        assert document.processing_error is None
        assert document.processing_warning == "OCR is unavailable; the image was retained without extracted text."
        assert document.ocr_mode == "unavailable"
        assert db.scalars(select(Passage).where(Passage.document_id == document_id)).all() == []


@pytest.mark.parametrize(
    ("mode", "detail"),
    [
        ("external", "external relationships"),
        ("encrypted", "Encrypted Office files"),
        ("macro", "Macro-enabled Office files"),
    ],
)
def test_unsafe_office_containers_are_rejected_at_upload(tmp_path: Path, mode: str, detail: str):
    fixture = tmp_path / f"{mode}.docx"
    _office_fixture(fixture, mode)
    with _asgi_client() as client:
        workspace_id = _workspace(client, f"office-{mode}")
        response = _post_file(client, workspace_id, fixture)
    assert response.status_code == 415
    assert detail in response.json()["detail"]
    assert "traceback" not in response.text.lower()


def test_extraction_timeout_terminates_child_process(monkeypatch, tmp_path: Path):
    class Receive:
        def poll(self, _timeout):
            return False

        def close(self):
            return None

    class Send:
        def close(self):
            return None

    class Process:
        terminated = False
        alive = True

        def start(self):
            return None

        def terminate(self):
            self.terminated = True
            self.alive = False

        def join(self, _timeout):
            return None

        def is_alive(self):
            return self.alive

        def close(self):
            return None

    process = Process()

    class Context:
        def Pipe(self, *, duplex):
            assert duplex is False
            return Receive(), Send()

        def Process(self, **_kwargs):
            return process

    monkeypatch.setattr(processing_module.multiprocessing, "get_context", lambda mode: Context())
    with pytest.raises(TimeoutError, match="exceeded the time limit"):
        processing_module.extract_isolated(tmp_path / "slow.pdf", "pdf")
    assert process.terminated and not process.is_alive()
