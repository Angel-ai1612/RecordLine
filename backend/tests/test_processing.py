import hashlib
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import Document, Fact, Passage, Workspace
from app.processing import process_document


def test_processing_pipeline_reaches_ready_with_evidence():
    init_db()
    source = Path(__file__).parent / "data" / "medsaathi_proposal.pdf"
    with SessionLocal() as db:
        db.add(Workspace(id="ws-processing", name="Processing integration"))
        db.add(
            Document(
                id="doc-processing", workspace_id="ws-processing", filename=source.name,
                stored_path=str(source), sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                file_type="pdf", status="queued",
            )
        )
        db.commit()
    process_document("doc-processing")
    with SessionLocal() as db:
        document = db.get(Document, "doc-processing")
        assert document is not None and document.status == "ready"
        passages = db.scalars(select(Passage).where(Passage.document_id == document.id)).all()
        facts = db.scalars(select(Fact).where(Fact.document_id == document.id)).all()
        assert any(p.page == 3 for p in passages)
        assert any(f.field == "project_budget" and f.normalized_value == "50000" and f.status == "approved" for f in facts)
        assert all(db.get(Passage, fact.passage_id) is not None for fact in facts)
