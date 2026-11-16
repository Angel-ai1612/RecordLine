from __future__ import annotations

import gc
import hashlib
import logging
import multiprocessing
import os
import re
import tempfile
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

from fastapi import HTTPException, UploadFile
from PIL import Image
from sqlalchemy import select, update

from .analysis import analyze_document, recompute_workspace, uid
from .config import settings
from .database import SessionLocal
from .extraction import OCR, extract
from .models import Document, Passage


logger = logging.getLogger("doctrace.processing")
executor = ThreadPoolExecutor(max_workers=settings.worker_count, thread_name_prefix="doctrace")
_job_slots = threading.BoundedSemaphore(settings.worker_count + settings.max_pending_jobs)
_workspace_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


ALLOWED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
}


class ProcessingQueueFull(RuntimeError):
    pass


def safe_display_name(value: str | None) -> str:
    name = Path((value or "upload").replace("\\", "/")).name
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return name[:255] or "upload"


def _workspace_lock(workspace_id: str) -> threading.Lock:
    with _locks_guard:
        return _workspace_locks.setdefault(workspace_id, threading.Lock())


def _validate_zip(path: Path, file_type: str) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > settings.max_zip_entries:
                raise ValueError("Office file contains too many entries")
            total = 0
            names = set()
            for info in infos:
                pure = PurePosixPath(info.filename)
                if pure.is_absolute() or ".." in pure.parts:
                    raise ValueError("Office file contains an unsafe path")
                total += info.file_size
                if total > settings.max_zip_uncompressed:
                    raise ValueError("Office file expands beyond the limit")
                if info.compress_size == 0 and info.file_size > 0:
                    raise ValueError("Office file has an invalid compression ratio")
                if info.compress_size and info.file_size / info.compress_size > settings.max_zip_ratio:
                    raise ValueError("Office file compression ratio is unsafe")
                if info.flag_bits & 0x1:
                    raise ValueError("Encrypted Office files are not supported")
                names.add(info.filename)
            required = "word/document.xml" if file_type == "docx" else "xl/workbook.xml"
            if required not in names or "[Content_Types].xml" not in names:
                raise ValueError("Office container does not match its extension")
            content_types = archive.read("[Content_Types].xml").lower()
            if b"vbaproject" in content_types or b"macroenabled" in content_types:
                raise ValueError("Macro-enabled Office files are not supported")
            for name in names:
                if name.lower().endswith(".rels"):
                    relationships = archive.read(name).lower()
                    if re.search(br"targetmode\s*=\s*['\"]external['\"]", relationships):
                        raise ValueError("Office files with external relationships are not supported")
    except zipfile.BadZipFile as exc:
        raise ValueError("Office file is corrupted") from exc


def validate_file(path: Path, extension: str, file_type: str) -> None:
    size = path.stat().st_size
    if size == 0:
        raise ValueError("File is empty")
    head = path.read_bytes()[:16]
    if file_type == "pdf":
        if not head.startswith(b"%PDF-"):
            raise ValueError("File content does not match the PDF extension")
        try:
            import pymupdf as fitz

            pdf = None
            try:
                pdf = fitz.open(path)
                if pdf.needs_pass:
                    raise ValueError("Encrypted PDFs are not supported")
                if pdf.page_count > settings.max_pdf_pages:
                    raise ValueError("PDF exceeds the page limit")
            finally:
                if pdf is not None:
                    pdf.close()
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("PDF is corrupted") from exc
    elif file_type in {"docx", "xlsx"}:
        if not head.startswith(b"PK"):
            raise ValueError("File content does not match the Office extension")
        _validate_zip(path, file_type)
    elif file_type == "image":
        expected = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG"}[extension]
        try:
            with Image.open(path) as image:
                if image.format != expected:
                    raise ValueError("File content does not match the image extension")
                if image.width * image.height > settings.max_image_pixels:
                    raise ValueError("Image exceeds the pixel limit")
                image.verify()
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Image is corrupted") from exc


def _unlink_with_retry(path: Path, attempts: int = 6) -> bool:
    """Remove a temporary upload despite short-lived Windows reader locks."""
    for attempt in range(attempts):
        try:
            path.unlink(missing_ok=True)
            return True
        except PermissionError:
            gc.collect()
            if attempt + 1 < attempts:
                time.sleep(0.05 * (attempt + 1))
        except FileNotFoundError:
            return True
        except OSError:
            break
    logger.warning("temporary_upload_cleanup_failed")
    return False


async def save_upload(upload: UploadFile) -> tuple[str, str, Path, str, str]:
    display_name = safe_display_name(upload.filename)
    extension = Path(display_name).suffix.lower()
    file_type = ALLOWED_EXTENSIONS.get(extension)
    if not file_type:
        raise HTTPException(status_code=415, detail="Unsupported file type")
    digest = hashlib.sha256()
    total = 0
    temp_path: Path | None = None
    try:
        fd, raw_path = tempfile.mkstemp(prefix="doctrace-", suffix=extension, dir=settings.files_dir)
        os.close(fd)
        temp_path = Path(raw_path)
        with temp_path.open("wb") as target:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > settings.max_upload_bytes:
                    raise HTTPException(status_code=413, detail="File exceeds the 25 MB limit")
                digest.update(chunk)
                target.write(chunk)
        try:
            validate_file(temp_path, extension, file_type)
        except ValueError as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from exc
        doc_id = f"doc-{uuid.uuid4().hex}"
        final_path = settings.files_dir / f"{doc_id}{extension}"
        temp_path.replace(final_path)
        temp_path = None
        return doc_id, display_name, final_path, digest.hexdigest(), file_type
    finally:
        await upload.close()
        if temp_path and temp_path.exists():
            _unlink_with_retry(temp_path)


def _run_queued(document_id: str) -> None:
    try:
        process_document(document_id)
    finally:
        _job_slots.release()


def enqueue(document_id: str) -> None:
    if not _job_slots.acquire(blocking=False):
        raise ProcessingQueueFull("Document processing queue is full")
    try:
        executor.submit(_run_queued, document_id)
    except Exception:
        _job_slots.release()
        raise


def _extract_child(path: str, file_type: str, connection) -> None:
    """Spawn target: never return raw exception text or document content."""
    try:
        connection.send(("ok", extract(Path(path), file_type)))
    except BaseException as exc:
        connection.send(("error", type(exc).__name__))
    finally:
        connection.close()


def extract_isolated(path: Path, file_type: str):
    context = multiprocessing.get_context("spawn")
    receive, send = context.Pipe(duplex=False)
    process = context.Process(target=_extract_child, args=(str(path), file_type, send), daemon=True)
    process.start()
    send.close()
    try:
        if not receive.poll(settings.extraction_timeout_seconds):
            process.terminate()
            process.join(5)
            if process.is_alive() and hasattr(process, "kill"):
                process.kill()
                process.join(5)
            raise TimeoutError("Document extraction exceeded the time limit")
        status, payload = receive.recv()
        process.join(5)
        if status != "ok":
            raise ValueError(f"Document extraction failed during {payload}")
        return payload
    finally:
        receive.close()
        if process.is_alive():
            process.terminate()
            process.join(5)
        process.close()


def _set_status(document_id: str, status: str, *, error: str | None = None) -> None:
    with SessionLocal() as db:
        db.execute(update(Document).where(Document.id == document_id).values(status=status, processing_error=error))
        db.commit()


def process_document(document_id: str) -> None:
    try:
        _set_status(document_id, "extracting")
        with SessionLocal() as db:
            document = db.get(Document, document_id)
            if not document:
                return
            if document.file_type == "image":
                document.status = "ocr"
                db.commit()
            result = extract_isolated(Path(document.stored_path), document.file_type)
            if result.used_ocr and document.status != "ocr":
                document.status = "ocr"
                db.commit()
            db.refresh(document)
            document.file_date = result.file_date
            document.processing_warning = result.warning
            document.ocr_mode = OCR.mode if result.used_ocr else None
            document.status = "analyzing"
            for ordinal, item in enumerate(result.passages, start=1):
                db.add(
                    Passage(
                        id=uid("pas"), document_id=document.id, ordinal=ordinal, text=item.text,
                        page=item.page, paragraph_id=item.paragraph_id, sheet=item.sheet, cell=item.cell,
                        ocr_confidence=item.ocr_confidence,
                    )
                )
            db.commit()

        with SessionLocal() as db:
            document = db.get(Document, document_id)
            if not document:
                return
            analyze_document(db, document)
            document.status = "ready"
            db.flush()
            with _workspace_lock(document.workspace_id):
                recompute_workspace(db, document.workspace_id)
                db.commit()
        logger.info("document_processed id=%s", document_id)
    except Exception as exc:
        logger.warning("document_failed id=%s error_type=%s", document_id, type(exc).__name__)
        try:
            _set_status(document_id, "failed", error=f"Processing failed during {type(exc).__name__}")
        except Exception:
            logger.exception("status_update_failed id=%s", document_id)


def recover_interrupted_jobs() -> None:
    with SessionLocal() as db:
        rows = db.scalars(select(Document).where(Document.status.in_(["extracting", "ocr", "analyzing"]))).all()
        for row in rows:
            row.status = "failed"
            row.processing_error = "Processing was interrupted; upload the file again."
        db.commit()

