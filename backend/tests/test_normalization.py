from datetime import date

from sqlalchemy import select

from app.analysis import PROJECT_RE, analyze_document, fact_status, normalize_amount, parse_dates
from app.database import SessionLocal, init_db
from app.models import Document, Fact, Passage, Workspace


def test_amount_variants_are_normalized_deterministically():
    assert normalize_amount("50,000") == "50000"
    assert normalize_amount("1.5", "lakh") == "150000"
    assert normalize_amount("4,25O") == "4250"


def test_dates_support_day_first_and_english_month_forms():
    assert ("20/11/2026", date(2026, 11, 20)) in parse_dates("due 20/11/2026")
    assert any(value == date(2026, 11, 20) for _raw, value in parse_dates("Nov 20, 2026"))


def test_status_words_never_infer_approval():
    assert fact_status("The team proposed Rs 65,000") == "proposed"
    assert fact_status("The crew asked for Rs 88,000") == "proposed"
    assert fact_status("The committee sanctioned INR 65000") == "approved"
    assert fact_status("The total is INR 65000") == "stated"


def test_negated_project_mentions_are_not_linking_entities():
    assert PROJECT_RE.findall("IT IS NOT PROJECT HL-2027-02") == []
    assert PROJECT_RE.findall("NO MS-2026-01 DOCUMENT IS REFERENCED") == []
    assert PROJECT_RE.findall("MEDSAATHI MS-2026-01") == ["MS-2026-01"]


def test_bare_numeric_xlsx_budget_is_parsed_without_regex_group_error(tmp_path):
    init_db()
    with SessionLocal() as db:
        workspace = Workspace(id="ws-bare-budget", name="Bare budget regression")
        document = Document(
            id="doc-bare-budget", workspace_id=workspace.id, filename="budget.xlsx",
            stored_path=str(tmp_path / "budget.xlsx"), sha256="0" * 64,
            file_type="xlsx", status="analyzing",
        )
        db.add(workspace); db.add(document); db.flush()
        db.add(Passage(id="pas-bare-budget", document_id=document.id, ordinal=1, text="Summary!A12=Total budget | B12=65000", sheet="Summary", cell="B12"))
        db.flush()
        analyze_document(db, document)
        fact = db.scalar(select(Fact).where(Fact.document_id == document.id, Fact.field == "project_budget"))
        assert fact is not None and fact.normalized_value == "65000"
        db.rollback()

