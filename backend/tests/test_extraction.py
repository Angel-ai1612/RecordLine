from pathlib import Path

import fitz
from docx import Document
from openpyxl import Workbook

from app.extraction import extract_docx, extract_pdf, extract_xlsx


def test_pdf_preserves_page_locator(tmp_path: Path):
    path = tmp_path / "sample.pdf"
    pdf = fitz.open()
    for number in range(1, 4):
        page = pdf.new_page(); page.insert_text((72, 72), f"Page {number} evidence with enough text for extraction.")
    pdf.save(path)
    result = extract_pdf(path)
    assert any(p.page == 3 and "Page 3" in p.text for p in result.passages)


def test_docx_preserves_paragraphs_and_table_rows(tmp_path: Path):
    path = tmp_path / "sample.docx"
    doc = Document(); doc.add_heading("Heading", 1); doc.add_paragraph("A paragraph")
    table = doc.add_table(rows=1, cols=2); table.cell(0, 0).text = "Budget"; table.cell(0, 1).text = "Rs 50,000"
    doc.save(path)
    result = extract_docx(path)
    assert any(p.paragraph_id and p.paragraph_id.startswith("table-") for p in result.passages)


def test_xlsx_preserves_sheet_and_value_cell(tmp_path: Path):
    path = tmp_path / "sample.xlsx"
    wb = Workbook(); ws = wb.active; ws.title = "Summary"; ws["A12"] = "Total budget"; ws["B12"] = 65000
    wb.create_sheet("Revision Log")["A1"] = "Revision"; wb.save(path)
    result = extract_xlsx(path)
    row = next(p for p in result.passages if "65000" in p.text)
    assert row.sheet == "Summary" and row.cell == "B12"

