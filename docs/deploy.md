# RECORDLINE Local Operations Guide

RECORDLINE is not approved for a public or multi-user deployment. This guide covers a single Windows user running both services on loopback. `doctrace.db` and `DOCTRACE_*` are retained implementation compatibility identifiers.

## Supported boundary

- Backend: `127.0.0.1:8000` only.
- Frontend: the local Vite URL, normally `127.0.0.1:8080`.
- Storage: `backend/data/doctrace.db` plus `backend/data/files/`.
- No authentication, remote TLS, public ingress, cloud processor, telemetry, or runtime model download.

Binding to `0.0.0.0`, forwarding the port, using a tunnel, or placing the API behind a reverse proxy changes the trust model and is unsupported. Before that change, add authentication, object authorization, TLS, CSRF/session controls where relevant, quotas, deletion/export, an incident plan, and a fresh security/privacy assessment.

## Install and start

From the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
npm install
Copy-Item .env.example .env.local
.\.venv\Scripts\python.exe backend\tests\make_test_data.py
```

Start separately:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

```powershell
npm run dev
```

Or, with a Python 3.11 virtual environment:

```powershell
npm run dev:all
```

The actual verification host had Python 3.12.14. Backend unit/regression tests and evaluation ran there, but the combined runner correctly rejected it because production support is explicitly Python 3.11. Complete the Python 3.11 release check before distributing a release.

## Smoke and acceptance checks

With the backend running:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
.\.venv\Scripts\python.exe backend\scripts\load_demo.py
.\.venv\Scripts\python.exe backend\smoke.py
```

Expected health fields are `status`, `similarityMode`, and `ocrMode`. The demo loader must finish with all documents `ready` or explain any document-local failure. The smoke script must exit zero after dereferencing all evidence IDs.

Run the reproducible checks before a local release:

```powershell
.\.venv\Scripts\python.exe backend\tests\make_test_data.py
.\.venv\Scripts\python.exe -m pytest -q backend\tests
.\.venv\Scripts\python.exe -m pytest -q backend\tests
npm test
npm run build
.\.venv\Scripts\python.exe backend\evaluate.py
```

Evaluation writes the current, small-synthetic-data results to `evaluation_report.md`. Relationship precision is calculated only across annotated positive and must-not-link pairs; unlabelled predicted pairs remain unknown, so it is labelled precision rather than exhaustive-corpus precision. The current 100% synthetic scores are regression evidence, not real-world accuracy claims.

## Runtime checks

Before importing real documents:

- Confirm `/health` reports the expected OCR and similarity modes.
- Confirm the backend log shows only generated IDs, stages, durations/modes, and safe error types; it must not contain raw filenames, passages, questions, or answers.
- Confirm the process is listening only on `127.0.0.1`.
- Confirm `backend/data/` is excluded from source control and protected by OS account permissions/full-disk encryption.
- Confirm free disk space is sufficient for originals, the SQLite database, temporary uploads, and backups.

Processing uses a bounded queue and a spawned extraction process with a deadline. On queue saturation, the upload is removed and the API returns a safe busy response. A timeout or parser failure marks only the affected document failed. Startup marks interrupted `extracting`, `ocr`, or `analyzing` rows failed with a request to upload again.

## Consistent backup

Back up only while the backend is stopped. This ensures the main database, any SQLite sidecars, and uploaded originals represent one point in time.

```powershell
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupRoot = Join-Path (Resolve-Path .) "backups\doctrace-$stamp"
New-Item -ItemType Directory -Path $backupRoot | Out-Null
Copy-Item -LiteralPath backend\data -Destination $backupRoot -Recurse
Get-ChildItem -LiteralPath $backupRoot -Recurse | Get-FileHash -Algorithm SHA256 |
  Export-Csv -LiteralPath (Join-Path $backupRoot 'sha256.csv') -NoTypeInformation
```

Store the backup on an encrypted, access-controlled volume. Apply the same retention decision to originals, extracted data, and every backup. A database-only backup is incomplete.

## Restore test and restore

Restoring overwrites local runtime data. Stop the backend, preserve the current `backend/data/` as a separate recovery copy, and verify the selected backup path before copying it into place.

1. Check `sha256.csv` against the files in the backup.
2. Confirm the backup contains the database and `files/` from the same timestamp.
3. Move the current `backend/data/` aside rather than deleting it.
4. Copy the backed-up `data/` directory to `backend/data/`.
5. Start the backend, call `/health`, list workspaces/documents, open several evidence passages, and run `backend/smoke.py` with a restored workspace ID.
6. Keep the previous data copy until the restored workspace has been inspected.

Do not test restore against the only copy of real data. Schedule a periodic restore exercise using a separate working copy.

## Recovery and rollback

If a document is left active after a crash, restart the backend. Startup converts interrupted active states to `failed`; re-upload only that file. Do not edit the SQLite status manually.

For a code rollback in a Lovable-connected repository, preserve published history. Use a normal revert/forward-fix commit or a separate known-good working copy; never use force-push, rebase, reset of published history, amend, or squash. Keep the database/files backup paired with the code version that created it. Schema migrations are not yet versioned, so test rollback against a copy first.

After any rollback:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
.\.venv\Scripts\python.exe backend\smoke.py
npm test
```

## Monitoring and incident basics

This local build has no hosted uptime monitor, error tracker, alerting service, or durable queue dashboard. Watch the server console for safe stage/failure messages and use `/health` for capability status. Before broader use, add privacy-safe queue depth, processing duration, disk-space alerts, error correlation IDs, and restore monitoring.

If the device or backup may be compromised, stop the service without destroying evidence, disconnect unsupported remote access, preserve privacy-safe logs, identify affected originals/database/backups, rotate any exposed credentials, assess notification duties with qualified counsel, restore from a verified clean backup, and record corrective actions.

## Release blockers and deferred work

- Run the complete suite on Python 3.11 and add a 3.11 CI job.
- Produce a resolved/hash-locked Python dependency set and run a dependency/license audit.
- Expand independent annotations so relationship precision can be measured across every candidate pair, not only labelled positives and must-not-link traps.
- Add deletion/export and retention workflows before processing real personal data at scale.
- Add stronger OS/container parser sandboxing before accepting public hostile uploads.
- Split or lazy-load the frontend entry bundle if first-load performance matters.
- Add a supported email importer before advertising `.txt` or `.eml`; both are currently rejected.

Cloud capacity and cost estimates for 100 or 10,000 users are intentionally omitted because remote/multi-user hosting is outside the approved architecture. Estimating them without authentication, tenancy, quotas, storage retention, and a workload profile would be misleading.
