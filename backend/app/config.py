from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]


def _origins(value: str) -> tuple[str, ...]:
    return tuple(x.strip() for x in value.split(",") if x.strip())


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DOCTRACE_DATABASE_URL", f"sqlite:///{(BACKEND_DIR / 'data' / 'doctrace.db').as_posix()}"
    )
    files_dir: Path = Path(os.getenv("DOCTRACE_FILES_DIR", str(BACKEND_DIR / "data" / "files")))
    max_upload_bytes: int = int(os.getenv("DOCTRACE_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
    max_question_chars: int = 2000
    max_search_chars: int = 500
    max_pdf_pages: int = 500
    max_image_pixels: int = 50_000_000
    max_zip_entries: int = 2500
    max_zip_uncompressed: int = 150 * 1024 * 1024
    max_zip_ratio: int = 200
    worker_count: int = max(1, min(int(os.getenv("DOCTRACE_WORKERS", "2")), 4))
    max_pending_jobs: int = max(1, min(int(os.getenv("DOCTRACE_MAX_PENDING_JOBS", "8")), 64))
    extraction_timeout_seconds: int = max(5, int(os.getenv("DOCTRACE_EXTRACTION_TIMEOUT_SECONDS", "120")))
    cors_origins: tuple[str, ...] = _origins(
        os.getenv(
            "DOCTRACE_CORS_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8080,http://localhost:8080",
        )
    )
    seed_default_workspace: str | None = os.getenv("SEED_DEFAULT_WORKSPACE") or None
    similarity_mode: str = os.getenv("DOCTRACE_SIMILARITY_MODE", "tfidf")


settings = Settings()
settings.files_dir.mkdir(parents=True, exist_ok=True)

