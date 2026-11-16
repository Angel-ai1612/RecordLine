# RECORDLINE

RECORDLINE is a local, evidence-first document intelligence workbench. It ingests PDF, DOCX, XLSX, PNG, and JPEG files; extracts source passages; links related documents; flags potential inconsistencies; builds a dated timeline; and answers questions with citations that open the underlying passage.

Read the complete [RECORDLINE technical documentation](docs/RECORDLINE.md) for objectives, architecture, languages/frameworks, algorithms, methodology, UML/use-case/context diagrams, API overview, data model, operations, and limitations. Existing `DOCTRACE_*` environment-variable names and `doctrace.db` are implementation compatibility identifiers.

The backend is intentionally local and private. It binds to `127.0.0.1`, makes no runtime LLM or network calls, and stores the SQLite database and uploaded originals under `backend/data/`. It does not decide which conflicting value is correct.

## Requirements

- Windows PowerShell
- Python 3.11
- Node.js and npm
- About 1 GB of free space for the virtual environment, frontend dependencies, generated corpus, database, and OCR runtime

This project is connected to Lovable. Do not force-push, rebase, amend, or squash commits that are already published; use ordinary forward commits or revert commits so Lovable history remains intact.

## First-time setup

Run these commands from the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
npm install
Copy-Item .env.example .env.local
```

`backend/requirements.txt` currently installs RapidOCR and its bundled ONNX runtime so the generated noisy receipt can be evaluated offline after installation. If RapidOCR cannot be imported, RECORDLINE starts with `ocrMode: "unavailable"`; scanned files are retained with a warning and no OCR text is invented. A separate lightweight dependency profile is not yet provided.

## Generate the deterministic test corpus

```powershell
.\.venv\Scripts\python.exe backend\tests\make_test_data.py
```

The generator has a fixed seed and writes development data, independent ground truth, robustness fixtures, and held-out projects under `backend/tests/data/`. It verifies that the chosen TrueType font round-trips the rupee sign through PDF extraction. Set `DOCTRACE_TEST_FONT` to another TrueType font containing U+20B9 if none of the built-in Windows/Linux candidates is available.

`.txt` and `.eml` ingestion are not supported.

## Run RECORDLINE

Use two PowerShell windows.

Backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
npm run dev
```

Open the Vite URL printed in the frontend terminal, normally `http://127.0.0.1:8080`. `.env.local` selects the real HTTP API at `http://127.0.0.1:8000`. Delete or empty `VITE_API_BASE_URL` to use session-only mock data instead.

On Python 3.11, both servers can be launched together:

```powershell
npm run dev:all
```

The combined runner deliberately refuses other Python versions. It streams both servers and stops both when one fails or when you press Ctrl+C.

## Load and inspect the generated demo

With the backend running:

```powershell
.\.venv\Scripts\python.exe backend\scripts\load_demo.py
.\.venv\Scripts\python.exe backend\smoke.py
```

`load_demo.py` creates a workspace through the API, uploads every development document, and polls until each reaches `ready` or `failed`. `smoke.py` calls the endpoints in the same order as the UI and dereferences answer, relationship, and timeline evidence.

The workspace UI is at `/workspaces`. Open a workspace to use Documents, Graph, Conflicts, Timeline, Ask, and Audit. Reviews are stored as `pending`, `confirmed`, or `rejected`; rejected relationships are excluded from later conflict clustering.

## Health and active modes

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

The response reports `status`, the active `similarityMode`, and `ocrMode`. Startup logs report the same capability modes without document content.

## Tests and evaluation

```powershell
.\.venv\Scripts\python.exe -m pytest -q backend\tests
npm test
npm run build
.\.venv\Scripts\python.exe backend\evaluate.py
```

The evaluation runs keyword/entity, semantic TF-IDF, and hybrid methods on separate development and held-out sets and rewrites `evaluation_report.md`. The held-out set is never used for threshold or weight tuning.

Current synthetic evaluation snapshot:

- Hybrid relationship labelled precision/recall/F1: 100%/100%/100% on development and held-out annotations, with zero labelled must-not-link violations. Unlabelled predicted pairs are unknown rather than counted as false positives; this is not exhaustive-corpus precision.
- Hybrid conflict precision/recall: 100%/100% on both splits.
- Fact and OCR amount accuracy: 100% for the labelled development cases; held-out contains no OCR-labelled amount.
- Strengthened evidence accuracy: 100% development (12/12) and held-out (4/4).
- Exact timeline accuracy: 100% development (10/10) and held-out (6/6).
- Semantic-only TF-IDF relationship recall: 0% on both splits.

These figures are from a tiny generated corpus and are regression evidence only, not general accuracy claims. See [evaluation_report.md](evaluation_report.md) for denominators, per-format timings, metric definitions, and the exact active modes.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | unset | Frontend API switch; `.env.local` sets `http://127.0.0.1:8000` |
| `DOCTRACE_DATABASE_URL` | `sqlite:///backend/data/doctrace.db` | SQLAlchemy database URL |
| `DOCTRACE_FILES_DIR` | `backend/data/files` | Uploaded-original storage |
| `DOCTRACE_MAX_UPLOAD_BYTES` | 25 MiB | Streaming upload limit |
| `DOCTRACE_WORKERS` | `2` | Active background workers, clamped to 1-4 |
| `DOCTRACE_MAX_PENDING_JOBS` | `8` | Pending queue capacity, clamped to 1-64 |
| `DOCTRACE_EXTRACTION_TIMEOUT_SECONDS` | `120` | Killable extraction-process deadline |
| `DOCTRACE_CORS_ORIGINS` | exact localhost/127.0.0.1 ports 5173 and 8080 | Allowed Vite origins |
| `DOCTRACE_SIMILARITY_MODE` | `tfidf` | Reported local similarity mode |
| `SEED_DEFAULT_WORKSPACE` | unset | Optional idempotent default-workspace ID |
| `DOCTRACE_TEST_FONT` | auto-detected | Test generator font containing the rupee glyph |

Do not put secrets or document content in environment variables or logs.

## Data, backup, and limitations

SQLite, WAL/SHM sidecars, and `backend/data/files/` form one consistency unit. Stop the backend before copying or restoring them. See [docs/deploy.md](docs/deploy.md) for a safe backup, restore, health check, recovery, and rollback procedure.

Known boundaries:

- This is a loopback-only, single-user product with no authentication, user authorization, remote TLS, deletion/export API, or durable external job queue.
- Do not expose it through `0.0.0.0`, a reverse proxy, port forwarding, or a tunnel.
- Parser work is bounded and time-limited in child processes, but a public hostile-upload service requires stronger OS/container sandboxing and quotas.
- The current frontend build succeeds but warns about an initial client chunk near 550 kB.
- The working environment used for the 2026-11-15 verification had Python 3.12.14. Python 3.11 is the supported target and enforced by `npm run dev:all`, but a Python 3.11 run was not available on that machine and remains a release check.
- Local processing does not remove privacy obligations. Protect the device and backups, define retention, and obtain qualified security/privacy/legal review before real regulated or commercial use.

Architecture decisions live in [ARCHITECTURE.md](ARCHITECTURE.md). Security, privacy, accessibility, and blind-spot reviews are under `docs/`.

