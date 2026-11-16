from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pymupdf as fitz
from docx import Document as DocxDocument
from openpyxl import load_workbook
from PIL import Image, ImageEnhance, ImageFilter

from .config import settings


@dataclass
class ExtractedPassage:
    text: str
    page: int | None = None
    paragraph_id: str | None = None
    sheet: str | None = None
    cell: str | None = None
    ocr_confidence: float | None = None


@dataclass
class ExtractionResult:
    passages: list[ExtractedPassage]
    file_date: date | None
    used_ocr: bool = False
    warning: str | None = None


class OcrEngine:
    mode = "unavailable"

    def read(self, image: Image.Image) -> tuple[str, float | None]:
        return "", None


class RapidOcrEngine(OcrEngine):
    mode = "rapidocr"

    def __init__(self) -> None:
        from rapidocr_onnxruntime import RapidOCR

        self._ocr = RapidOCR()

    def read(self, image: Image.Image) -> tuple[str, float | None]:
        prepared = image.convert("L")
        prepared = ImageEnhance.Contrast(prepared).enhance(1.7).filter(ImageFilter.MedianFilter(3))
        result, _elapsed = self._ocr(prepared)
        if not result:
            return "", None
        rows = sorted(result, key=lambda row: (min(p[1] for p in row[0]), min(p[0] for p in row[0])))
        text = "\n".join(str(row[1]).strip() for row in rows if str(row[1]).strip())
        scores = [float(row[2]) for row in rows if len(row) > 2]
        return text, (sum(scores) / len(scores) if scores else None)


def make_ocr_engine() -> OcrEngine:
    try:
        return RapidOcrEngine()
    except Exception:
        return OcrEngine()


OCR = make_ocr_engine()


def _safe_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        match = re.search(r"(\d{4})[-:]?(\d{2})[-:]?(\d{2})", value)
        if match:
            try:
                return date(*(int(x) for x in match.groups()))
            except ValueError:
                return None
    return None


def _mtime(path: Path) -> date:
    return datetime.fromtimestamp(path.stat().st_mtime).date()


def _image_metadata_date(image: Image.Image) -> date | None:
    """Read portable embedded image dates before falling back to file mtime."""
    try:
        exif = image.getexif()
    except Exception:
        exif = {}
    for tag in (36867, 36868, 306):  # DateTimeOriginal, DateTimeDigitized, DateTime
        parsed = _safe_date(exif.get(tag))
        if parsed:
            return parsed
    for key in (
        "Creation Time", "creation_time", "DateTimeOriginal", "DateTime", "date:create", "date",
    ):
        parsed = _safe_date(image.info.get(key))
        if parsed:
            return parsed
    return None


def extract_pdf(path: Path) -> ExtractionResult:
    passages: list[ExtractedPassage] = []
    used_ocr = False
    warning = None
    with fitz.open(path) as pdf:
        if pdf.page_count > settings.max_pdf_pages:
            raise ValueError("PDF exceeds the page limit")
        file_date = _safe_date(pdf.metadata.get("creationDate")) if pdf.metadata else None
        for page_index, page in enumerate(pdf):
            blocks = page.get_text("blocks")
            page_text = "".join(str(block[4]) for block in blocks).strip()
            if len(page_text) >= 20:
                for block_index, block in enumerate(blocks):
                    text = " ".join(str(block[4]).split())
                    if text:
                        passages.append(
                            ExtractedPassage(text=text, page=page_index + 1, paragraph_id=f"block-{block_index + 1}")
                        )
                continue
            used_ocr = True
            if OCR.mode == "unavailable":
                warning = "OCR is unavailable; image-only pages were retained without extracted text."
                continue
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            if image.width * image.height > settings.max_image_pixels:
                raise ValueError("Rasterized PDF page exceeds the pixel limit")
            text, confidence = OCR.read(image)
            if text:
                passages.append(
                    ExtractedPassage(
                        text=" ".join(text.split()),
                        page=page_index + 1,
                        paragraph_id="ocr-1",
                        ocr_confidence=confidence,
                    )
                )
    return ExtractionResult(passages, file_date or _mtime(path), used_ocr, warning)


def extract_docx(path: Path) -> ExtractionResult:
    doc = DocxDocument(path)
    passages: list[ExtractedPassage] = []
    ordinal = 0
    for paragraph in doc.paragraphs:
        text = " ".join(paragraph.text.split())
        if text:
            ordinal += 1
            passages.append(ExtractedPassage(text=text, paragraph_id=f"para-{ordinal}"))
    for table_index, table in enumerate(doc.tables, start=1):
        for row_index, row in enumerate(table.rows, start=1):
            values = [" ".join(cell.text.split()) for cell in row.cells]
            text = " | ".join(value for value in values if value)
            if text:
                passages.append(ExtractedPassage(text=text, paragraph_id=f"table-{table_index}-row-{row_index}"))
    return ExtractionResult(passages, _safe_date(doc.core_properties.created) or _mtime(path))


def extract_xlsx(path: Path) -> ExtractionResult:
    workbook = load_workbook(path, read_only=True, data_only=True, keep_links=False)
    passages: list[ExtractedPassage] = []
    try:
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows():
                cells = [cell for cell in row if cell.value not in (None, "")]
                if not cells:
                    continue
                parts = [f"{cell.coordinate}={cell.value}" for cell in cells]
                value_cell = next((cell.coordinate for cell in reversed(cells) if isinstance(cell.value, (int, float))), cells[-1].coordinate)
                passages.append(
                    ExtractedPassage(text=f"{sheet.title}!{' | '.join(parts)}", sheet=sheet.title, cell=value_cell)
                )
        created = getattr(workbook.properties, "created", None)
        return ExtractionResult(passages, _safe_date(created) or _mtime(path))
    finally:
        workbook.close()


def extract_image(path: Path) -> ExtractionResult:
    with Image.open(path) as image:
        file_date = _image_metadata_date(image) or _mtime(path)
        image.load()
        if image.width * image.height > settings.max_image_pixels:
            raise ValueError("Image exceeds the pixel limit")
        if OCR.mode == "unavailable":
            return ExtractionResult([], file_date, True, "OCR is unavailable; the image was retained without extracted text.")
        text, confidence = OCR.read(image)
    passages = [ExtractedPassage(text=" ".join(text.split()), page=1, ocr_confidence=confidence)] if text else []
    warning = None if passages else "OCR completed but did not find readable text."
    return ExtractionResult(passages, file_date, True, warning)


def extract(path: Path, file_type: str) -> ExtractionResult:
    if file_type == "pdf":
        return extract_pdf(path)
    if file_type == "docx":
        return extract_docx(path)
    if file_type == "xlsx":
        return extract_xlsx(path)
    if file_type == "image":
        return extract_image(path)
    raise ValueError("Unsupported file type")

