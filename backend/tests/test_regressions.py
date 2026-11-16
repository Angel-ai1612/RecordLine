from __future__ import annotations

import threading
import uuid
import zipfile
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from fastapi import HTTPException
from PIL import Image, PngImagePlugin
from sqlalchemy import select

from app import extraction, processing
from app.analysis import (
    _build_timeline,
    analyze_document,
    build_relationship_signals,
    parse_dates,
    recompute_workspace,
    select_relationship_evidence,
)
from app.config import settings
from app.database import SessionLocal, init_db
from app.models import Audit, Conflict, Document, Entity, Event, Passage, Relationship, Workspace


def test_pairwise_evidence_prefers_shared_amount_and_request_over_titles():
    left = Document(
        id="doc-evidence-left", workspace_id="ws-evidence", filename="team_meeting.docx",
        stored_path="left", sha256="a" * 64, file_type="docx", status="ready",
        file_date=date(2026, 11, 7),
    )
    right = Document(
        id="doc-evidence-right", workspace_id="ws-evidence", filename="budget_workbook.xlsx",
        stored_path="right", sha256="b" * 64, file_type="xlsx", status="ready",
        file_date=date(2026, 11, 10),
    )
    left_passages = [
        Passage(id="pas-left-title", document_id=left.id, ordinal=1, text="MedSaathi coordination meeting MS-2026-01"),
        Passage(id="pas-left-detail", document_id=left.id, ordinal=2, text="The meeting requested INR 65000 as the revised budget."),
    ]
    right_passages = [
        Passage(id="pas-right-title", document_id=right.id, ordinal=1, text="MedSaathi MS-2026-01 budget"),
        Passage(id="pas-right-detail", document_id=right.id, ordinal=2, text="Revision log: meeting requested INR 65000."),
    ]

    selected_left, selected_right = select_relationship_evidence(
        left_passages, right_passages, left, right
    )

    assert selected_left is not None and selected_left.id == "pas-left-detail"
    assert selected_right is not None and selected_right.id == "pas-right-detail"


def test_iso_story_date_creates_resolvable_file_date_event():
    init_db()
    suffix = uuid.uuid4().hex[:8]
    workspace_id = f"ws-timeline-{suffix}"
    document = Document(
        id=f"doc-timeline-{suffix}", workspace_id=workspace_id, filename="closeout.xlsx",
        stored_path="closeout.xlsx", sha256="c" * 64, file_type="xlsx", status="ready",
        file_date=date(2027, 1, 20),
    )
    passage = Passage(
        id=f"pas-timeline-{suffix}", document_id=document.id, ordinal=1,
        text="Revision!A2=2027-01-20 | B2=stated | C2=Close-out recorded",
        sheet="Revision", cell="A2:C2",
    )
    with SessionLocal() as db:
        db.add(Workspace(id=workspace_id, name=f"Timeline {suffix}"))
        db.add(document)
        db.add(passage)
        db.flush()
        _build_timeline(db, workspace_id, [document], {document.id: [passage]})
        db.commit()
        event = db.scalar(
            select(Event).where(
                Event.workspace_id == workspace_id,
                Event.document_id == document.id,
                Event.event_date == date(2027, 1, 20),
                Event.file_date == date(2027, 1, 20),
            )
        )
        assert event is not None and event.passage_id == passage.id
    assert parse_dates("Revision!A2=2027-01-20") == [("2027-01-20", date(2027, 1, 20))]


def test_image_story_dates_come_from_embedded_metadata_after_upload_copy(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(extraction, "OCR", extraction.OcrEngine())
    image = Image.new("RGB", (8, 8), "white")
    png_info = PngImagePlugin.PngInfo()
    png_info.add_text("Creation Time", "2026-11-09T12:00:00Z")
    png = tmp_path / "uploaded.png"
    image.save(png, "PNG", pnginfo=png_info)
    exif = Image.Exif()
    exif[306] = exif[36867] = "2026:11:09 12:00:00"
    jpg = tmp_path / "uploaded.jpg"
    image.save(jpg, "JPEG", exif=exif)

    assert extraction.extract_image(png).file_date == date(2026, 11, 9)
    assert extraction.extract_image(jpg).file_date == date(2026, 11, 9)


def test_runtime_relationship_signals_are_real_tfidf():
    left = Document(
        id="doc-left-signal", workspace_id="ws-signal", filename="left.pdf", stored_path="left",
        sha256="0" * 64, file_type="pdf", status="ready", file_date=date(2026, 1, 1),
    )
    right = Document(
        id="doc-right-signal", workspace_id="ws-signal", filename="right.pdf", stored_path="right",
        sha256="1" * 64, file_type="pdf", status="ready", file_date=date(2026, 1, 2),
    )
    passages = {
        left.id: [Passage(id="pas-left-signal", document_id=left.id, ordinal=1, text="alpha beta gamma")],
        right.id: [Passage(id="pas-right-signal", document_id=right.id, ordinal=1, text="alpha beta delta")],
    }
    signal = build_relationship_signals([left, right], passages, {left.id: set(), right.id: set()})[(left.id, right.id)]
    # Unigram/bigram TF-IDF cosine is neither binary token cosine nor a boolean overlap.
    assert 0.2 < signal["semanticSimilarity"] < 0.9
    assert settings.similarity_mode == "tfidf"


def test_recompute_preserves_review_ids_statuses_and_audit_targets():
    init_db()
    suffix = uuid.uuid4().hex[:8]
    workspace_id = f"ws-review-{suffix}"
    with SessionLocal() as db:
        db.add(Workspace(id=workspace_id, name=f"Review preservation {suffix}"))
        docs = [
            Document(
                id=f"doc-review-a-{suffix}", workspace_id=workspace_id, filename="proposal.pdf",
                stored_path="proposal.pdf", sha256="a" * 64, file_type="pdf", status="ready",
                file_date=date(2026, 11, 3),
            ),
            Document(
                id=f"doc-review-b-{suffix}", workspace_id=workspace_id, filename="revision.pdf",
                stored_path="revision.pdf", sha256="b" * 64, file_type="pdf", status="ready",
                file_date=date(2026, 11, 7),
            ),
        ]
        db.add_all(docs)
        db.flush()
        db.add_all([
            Passage(
                id=f"pas-review-a-{suffix}", document_id=docs[0].id, ordinal=1,
                text="Project RV-2026-01 budget Rs 50,000 was recorded on 3 November 2026.",
            ),
            Passage(
                id=f"pas-review-b-{suffix}", document_id=docs[1].id, ordinal=1,
                text="Project RV-2026-01 revised budget Rs 65,000 was recorded on 7 November 2026.",
            ),
        ])
        db.flush()
        for document in docs:
            analyze_document(db, document)
        db.flush()
        recompute_workspace(db, workspace_id)
        db.commit()

        relationship = db.scalar(select(Relationship).where(Relationship.workspace_id == workspace_id))
        conflict = db.scalar(select(Conflict).where(Conflict.workspace_id == workspace_id))
        assert relationship is not None and conflict is not None
        relationship.review_status = "confirmed"
        conflict.review_status = "rejected"
        db.add_all([
            Audit(
                id=f"aud-rel-{suffix}", workspace_id=workspace_id, target_type="relationship",
                target_id=relationship.id, action="confirmed", actor="local-user",
            ),
            Audit(
                id=f"aud-con-{suffix}", workspace_id=workspace_id, target_type="conflict",
                target_id=conflict.id, action="rejected", actor="local-user",
            ),
        ])
        db.commit()
        relationship_id, conflict_id = relationship.id, conflict.id

        recompute_workspace(db, workspace_id)
        db.commit()
        preserved_relationship = db.get(Relationship, relationship_id)
        preserved_conflict = db.get(Conflict, conflict_id)
        assert preserved_relationship is not None and preserved_relationship.review_status == "confirmed"
        assert preserved_conflict is not None and preserved_conflict.review_status == "rejected"
        targets = set(db.scalars(select(Audit.target_id).where(Audit.workspace_id == workspace_id)))
        assert {relationship_id, conflict_id} <= targets


def test_processing_queue_rejects_when_bounded_capacity_is_full(monkeypatch):
    slots = threading.BoundedSemaphore(1)
    assert slots.acquire(blocking=False)
    monkeypatch.setattr(processing, "_job_slots", slots)
    with pytest.raises(processing.ProcessingQueueFull):
        processing.enqueue("doc-will-not-run")


def test_office_external_relationships_are_rejected(tmp_path: Path):
    path = tmp_path / "external.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        archive.writestr("word/document.xml", "<document/>")
        archive.writestr(
            "word/_rels/document.xml.rels",
            '<Relationships><Relationship TargetMode = "External" Target="https://example.invalid/"/></Relationships>',
        )
    with pytest.raises(ValueError, match="external relationships"):
        processing.validate_file(path, ".docx", "docx")


def test_invalid_pdf_cleanup_retries_windows_lock_without_masking_415(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(processing, "settings", replace(settings, files_dir=tmp_path))
    monkeypatch.setattr(
        processing,
        "validate_file",
        lambda _path, _extension, _file_type: (_ for _ in ()).throw(ValueError("PDF is corrupted")),
    )
    original_unlink = Path.unlink
    attempts = 0

    def briefly_locked(path: Path, *args, **kwargs):
        nonlocal attempts
        if path.name.startswith("doctrace-"):
            attempts += 1
            if attempts < 3:
                raise PermissionError("simulated Windows reader lock")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", briefly_locked)
    class MemoryUpload:
        filename = "corrupted.pdf"

        def __init__(self):
            self.payloads = iter((b"%PDF-1.7\ntruncated", b""))
            self.closed = False

        async def read(self, _size: int) -> bytes:
            return next(self.payloads)

        async def close(self) -> None:
            self.closed = True

    upload = MemoryUpload()

    with pytest.raises(HTTPException) as caught:
        processing.save_upload(upload).send(None)

    assert caught.value.status_code == 415
    assert caught.value.detail == "PDF is corrupted"
    assert upload.closed
    assert attempts == 3
    assert not list(tmp_path.glob("doctrace-*"))


def test_default_cors_origins_cover_only_local_vite_ports():
    assert settings.cors_origins == (
        "http://127.0.0.1:5173", "http://localhost:5173",
        "http://127.0.0.1:8080", "http://localhost:8080",
    )
