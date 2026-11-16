# RECORDLINE Security Review

> “DocTrace” in historic evidence excerpts, paths, configuration names, and test names denotes the current implementation identifier. The reader-facing product name is RECORDLINE.

## Scope and trust boundary

Review date: 2026-11-14. This is the pre-implementation design gate for a single-user service that must bind only to `127.0.0.1`, accept untrusted PDF, DOCX, XLSX, PNG and JPEG uploads, and perform all parsing, OCR and analysis locally. The browser client sends an arbitrary workspace ID and resource IDs (`src/api/httpApi.ts:17-44`); the server is therefore responsible for validation and workspace ownership on every lookup and mutation. File contents, extracted passages and audit records are sensitive local data.

Authentication is intentionally out of scope only while the process is loopback-only and single-user. This boundary is not a security mechanism if the service is proxied, container-published, bound to `0.0.0.0`, or exposed through a tunnel. Any such change requires authentication, per-user authorization, CSRF protection where cookies are used, TLS, rate limits and a new threat model before use.

No production code existed when this review was written. A `Fail` below means the required control was not yet implemented or could not be verified; it is not a claim that a known-vulnerable implementation exists.

## Blocking design requirements

1. Stream uploads to a newly generated server-side filename while counting bytes; abort above 25 MiB and remove the partial file. Never join a client filename into a path. Keep the sanitized display name separately.
2. Allow only the contract formats in `src/api/types.ts:11`: PDF, DOCX, XLSX and image. Require an allowlisted extension **and** matching magic bytes/signature. Reject empty, corrupted, mismatched and unsupported files before creating a background job.
3. Treat DOCX/XLSX as hostile ZIP containers. Before extraction, cap entry count, total uncompressed bytes, per-entry bytes and compression ratio; reject encrypted archives, path traversal entries, external links and macro-enabled formats. Parse read-only/data-only and do not evaluate formulas.
4. Isolate expensive parsing/OCR from request handling with bounded workers, bounded queue depth and per-document time/memory/page/pixel limits. A timeout or parser crash must mark only that document `failed` with a safe reason.
5. Store originals under `backend/data/files/` outside any static web root. Use unpredictable document IDs, restrictive local permissions where supported, and atomic writes. Never execute, import or shell-open uploads.
6. Restrict CORS to explicit Vite origins such as `http://127.0.0.1:5173` and `http://localhost:5173`; allow only required methods/headers; do not combine wildcard origins with credentials.
7. Derive a resource's workspace from the database for `/documents/:id`, `/passages/:id`, `/relationships/:id` and `/conflicts/:id`. Workspace-list routes must filter in the query. PATCH routes must allow only the review-status enum and must derive audit workspace/target from the stored resource.
8. Use SQLAlchemy-bound parameters only; validate IDs, names, query length and question length. Return stable client-safe errors without parser exceptions, filesystem paths, SQL or extracted document text.
9. Enable SQLite foreign keys on every connection, use short transactions/WAL with a bounded write path, and make recompute replace workspace-derived records atomically. Preserve the previous usable state or roll back on failure.
10. Keep runtime offline: disable model telemetry and remote model downloads. Optional OCR/embedding/model discovery must use local paths only and fail closed to the documented fallback.
11. Never log document bodies, passages, questions, answers or raw filenames. Log generated IDs, stage, duration, mode and sanitized failure codes. Audit review mutations append immutable rows; application APIs must not update/delete audit history.
12. Provide a documented data-retention/deletion and backup policy before processing real documents. SQLite, originals and backups must be protected together; deleting only the database leaves source files behind.

High-severity items 1-5 and 7-10 block completion. The final security pass must inspect and test their implementation.

## Findings

### S-01 - High - hostile upload can escape storage or consume the host

- Evidence: upload is a raw multipart `File` sent to `/workspaces/:id/documents` (`src/api/httpApi.ts:19-30`); the frontend type declaration is not server-side validation (`src/api/types.ts:11`). Backend controls are not implemented yet.
- Exploit scenario: a crafted filename traverses out of the upload directory, a mismatched executable is accepted as an image, or a ZIP bomb/huge raster exhausts disk, RAM or CPU during Office parsing/OCR.
- Required fix: implement blocking requirements 1-5, including content signatures, Office ZIP expansion limits, image dimension limits, PDF page/object limits, randomized storage names, bounded workers and cleanup on every failure path.

### S-02 - High - workspace and resource isolation can be bypassed by ID

- Evidence: several fixed endpoints carry only a resource ID rather than the workspace (`src/api/httpApi.ts:33-41`), while the UI passes workspace IDs directly on list/search routes (`src/api/httpApi.ts:32,35-36,39,42-44`).
- Exploit scenario: a caller guesses or obtains another workspace's document, passage, relationship or conflict ID and reads or reviews it; a PATCH writes an audit entry under a client-chosen or wrong workspace.
- Required fix: use high-entropy IDs; fetch the target and its stored workspace in one query; derive audit scope from that row; apply workspace filters to all collection queries. Add negative cross-workspace endpoint tests. If the service ever becomes multi-user, add authenticated owner/role checks to every route.

### S-03 - High - parser/OCR failures can compromise availability or leak local data

- Evidence: the planned service invokes native PDF/OCR/model code over untrusted bytes and exposes status polling (`src/api/types.ts:12-21`, `src/api/hooks.ts:24-38`). No implementation can yet be checked for process isolation, timeouts or error redaction.
- Exploit scenario: malformed input crashes a native dependency, a very large image monopolizes OCR workers, or a raw exception returns a filesystem path and document fragment to the browser.
- Required fix: bounded process/worker execution with time, page, pixel, memory and queue limits; catch stage-specific failures; expose only a stable safe message; log no content; continue processing unrelated files.

### S-04 - High - remote exposure would provide unauthenticated document access

- Evidence: the fixed API has no authentication headers or session handling (`src/api/httpApi.ts:7-14`) and all create/read/review operations are callable directly (`src/api/httpApi.ts:17-44`). This is acceptable only under the stated loopback-only assumption.
- Exploit scenario: a later `0.0.0.0` bind, reverse proxy, port-forward or permissive container mapping exposes every stored document and review action to the network.
- Required fix: assert loopback host by default; document that remote exposure is unsupported; do not enable proxy trust casually. Before any network deployment, design authentication/authorization, TLS, CSRF/session controls, quotas and account-scoped storage.

### S-05 - Medium - CORS/configuration may expand browser access

- Evidence: the client API base URL is environment-controlled (`.env.example:1-2`); the backend CORS implementation does not yet exist.
- Exploit scenario: wildcard CORS lets an arbitrary web origin drive the local service from a victim's browser, upload hostile files and read extracted evidence where browser/network conditions permit.
- Required fix: exact-origin allowlist from configuration with safe local defaults, no regex/wildcards, required methods only, `allow_credentials=false` while unauthenticated, and tests for denied origins and preflight behavior.

### S-06 - Medium - derived-data recompute can corrupt evidence or audit integrity

- Evidence: graph, conflict, timeline and audit views are refetched when status changes (`src/api/hooks.ts:24-37`), and relationships/conflicts are mutable by review (`src/api/httpApi.ts:37-41`). Backend transaction behavior is not yet implemented.
- Exploit scenario: concurrent completion/recompute deletes evidence referenced by a result, rejected relationships reappear, or an audit row points to the wrong workspace/target.
- Required fix: foreign keys and uniqueness constraints; transactionally replace derived records; preserve rejected-review exclusions; append audit rows in the same transaction as review updates; test concurrent/failure rollback behavior.

### S-07 - Medium - sensitive local data lacks lifecycle controls

- Evidence: the planned database, originals, extracted passages, questions and answers contain arbitrary uploaded document data; no retention, delete, export, backup or encryption decision exists yet.
- Exploit scenario: originals remain after a workspace is believed removed, copied backups outlive the primary data, or another local OS account can read the database/files.
- Required fix: document retention and deletion semantics, delete originals and derived data together, recommend OS full-disk encryption and restrictive ACLs, exclude `backend/data/` from source control, and test backup/restore plus deletion before real use.

### S-08 - Medium - optional model/dependency behavior can violate offline/privacy guarantees

- Evidence: OCR/embedding/spaCy are planned optional dependencies; backend dependency files and startup logic do not yet exist.
- Exploit scenario: a library auto-downloads a model, emits telemetry, loads an untrusted local model artifact, or a native parser vulnerability is reachable through uploads.
- Required fix: pin compatible versions/hashes where practical, disable network/model downloads at runtime, use explicit trusted local model directories, publish active modes in `/health` without local paths, run dependency/license audits, and document patch/upgrade cadence.

### S-09 - Low - browser errors discard safe diagnostic detail

- Evidence: generic JSON requests expose only method/path/status (`src/api/httpApi.ts:12`) and upload errors expose only status (`src/api/httpApi.ts:25-27`).
- Exploit scenario: users cannot distinguish validation failures from service failures and may retry expensive operations repeatedly. This is operational rather than a data-exposure flaw.
- Required fix: backend returns a consistent safe error body and request ID. A later minimal frontend change may display the safe message, but no contract change is required for backend correctness.

## Design checklist

| Area | Result | Evidence / final-pass requirement |
| --- | --- | --- |
| Authentication | N/A | Deliberately absent for loopback-only, single-user use. Becomes Fail on any remote/multi-user exposure. |
| Authorization/object access | Fail | Resource-only endpoints exist (`src/api/httpApi.ts:33-41`); backend must derive and enforce stored workspace scope. |
| Input validation | Fail | No backend exists; validate body/query/path lengths, enums, IDs, multipart and signatures. |
| Parameterized database access | Fail | No backend exists; final review must confirm SQLAlchemy parameters and no dynamic SQL. |
| Output/error safety | Fail | No backend exists; parser/SQL/path/content details must never reach API errors. |
| CSRF | N/A | No cookies/authentication planned. Reassess before adding cookie-based sessions. |
| SSRF/external calls | Fail | Offline promise is unimplemented; final test must prove model startup and runtime perform no network downloads/calls. |
| File upload safety | Fail | No server-side allowlist, magic checks, expansion limits, randomized storage or resource limits yet. |
| Secrets/config | Pass | Existing frontend uses an environment base URL and contains no credential in `.env.example` (`.env.example:1-2`); backend secrets/config still require final review. |
| Dependency safety | Fail | Backend manifest/lock data does not exist yet; audit native parsers and licenses after implementation. |
| Transport/headers | N/A | HTTP is acceptable only on loopback. If exposed, TLS/HSTS and proxy configuration become mandatory. Add `X-Content-Type-Options` and frame/CSP policy as defense in depth. |
| CORS | Fail | Backend allowlist is not implemented; require exact local origins and denied-origin tests. |
| Logging/privacy | Fail | No logging implementation or retention/deletion policy exists; prohibit content/raw filenames and define lifecycle. |
| Rate/resource limits | Fail | Size limit alone is insufficient; require bounded queue, workers, OCR/page/pixel/time limits and question/search length limits. |
| Audit integrity | Fail | Schema/transactions do not exist; audit must be append-only and workspace derived from the reviewed target. |
| Encryption/backups/deletion | Fail | No lifecycle controls exist; document OS encryption, ACLs, backup/restore and complete deletion. |

## Final security gate test plan

- Upload: valid format matrix; empty; corrupted; extension/signature mismatch; unsupported; exactly-at/over 25 MiB; path traversal name; duplicate name; Office ZIP bomb/high-ratio archive; huge pixel dimensions; excessive PDF pages; encrypted Office/PDF; macro-enabled Office.
- Isolation: every resource and review endpoint with IDs from another workspace; invalid/high-volume IDs; audit workspace derived from target; rejected relationship excluded on recompute.
- Availability: parser crash/timeout, OCR timeout, full queue, disk-write failure and database lock affect only one document and yield a safe `failed` state.
- Privacy: inspect logs/errors for raw filename, content, question, answer, paths and stack traces; verify `backend/data/` ignore/permissions; delete/backup/restore behavior if implemented.
- Network: bind assertion for `127.0.0.1`; denied CORS origins; capture or block network while all fallback modes start and process the corpus.
- Integrity: SQLite foreign keys enabled; recompute rollback preserves prior state; evidence passage IDs always resolve; audit rows are append-only.

## Protections not requested but required before broader use

- Critical before remote use: authentication, per-user authorization, TLS, CSRF/session design, quotas and secure deletion/export.
- Should do before real documents: OS full-disk encryption, restrictive ACLs, tested encrypted backups, retention policy, dependency patch process and incident-response basics.
- Nice to have for local development: security headers, request correlation IDs, parser worker sandboxing under a lower-privilege OS account, and a one-command privacy-preserving diagnostic bundle.

This review is engineering guidance, not legal advice. Processing personal or regulated documents at scale requires a privacy impact assessment and qualified legal review.

## Final implementation gate - 2026-11-14

**Verdict: FAIL.** One High-severity finding remains open. The service must not be described as security-gate complete until F-01 is fixed and this gate is rerun. No Critical issue was found. This verdict is for the stated loopback-only, single-user scope; remote or multi-user exposure remains unsupported.

### Verification evidence

- `python -m pytest backend/tests -q` passed the original 13 tests in 3.46 seconds before the later security-test file appeared. A subsequent full run hung in `backend/tests/test_security.py`, which currently uses `fastapi.testclient.TestClient`; it was stopped after 60 seconds with no test result. The claimed ASGI transport replacement is not present in the inspected file.
- `python -m pip check` reported `No broken requirements found`.
- `npm audit --offline --audit-level=high` reported `found 0 vulnerabilities` using the installed lockfile.
- `pip-audit` was unavailable, so known-vulnerability status for Python packages is unverified. The installed packages were inventoried with `pip list --format=freeze`.
- A repository secret-pattern scan excluding generated documents, runtime data, dependencies, and the virtual environment found no candidate credential or private key. Git-history scanning was impossible because this directory is not a Git worktree.
- Static inspection verified streamed upload counting and cleanup, UUID storage names, extension and magic/container validation, Office archive traversal/expansion checks, PDF page and image pixel caps, exact CORS middleware, security headers, SQLite foreign keys/WAL, workspace-filtered collection queries, database-derived review/audit scope, append-only audit API behavior, generic background failure messages, and content-free routine logs.

### F-01 - High - untrusted parsers run in-process without a bounded queue or deadline

- **Location:** `backend/app/processing.py:26`, `backend/app/processing.py:153-154`, `backend/app/processing.py:163-210`.
- **Evidence:** `ThreadPoolExecutor` limits active workers but its `SimpleQueue` is unbounded. Each worker directly invokes PyMuPDF, python-docx, openpyxl, Pillow and RapidOCR in the API process. There is no per-document timeout, process boundary, memory limit, bounded submission semaphore, or queue-full response.
- **Exploit scenario:** a user opens a crafted but size-valid PDF, Office archive or image received from an untrusted source. Native parsing/OCR hangs, consumes excessive memory, or crashes; many uploads can also accumulate without bound. Both workers can become unavailable and a native crash can terminate the service, affecting unrelated documents.
- **Required fix:** put parsing/OCR in a killable subprocess with a per-document deadline and page/pixel/memory controls, and bound accepted queued jobs with explicit overload handling. At minimum for the local build, add a bounded submission semaphore/queue and a subprocess timeout that marks only the affected document failed. Add tests for queue saturation, parser timeout and worker crash. This was blocking requirement 4 in the early review.

### F-02 - Medium - Office preflight does not reject every disallowed container feature

- **Location:** `backend/app/processing.py:52-79`.
- **Evidence:** preflight caps entries, total expansion and compression ratio and rejects traversal, but it does not inspect ZIP encryption flags or external relationship targets. Macro-enabled extensions are excluded, but encrypted or externally linked `.docx`/`.xlsx` content is not explicitly rejected before enqueue.
- **Exploit scenario:** an encrypted Office entry or unusual external relationship passes upload validation and fails or behaves unexpectedly inside the background parser, consuming worker capacity and weakening the offline guarantee.
- **Required fix:** reject `ZipInfo.flag_bits & 0x1`; inspect Office relationship XML and reject external targets; add fixtures/tests. Keep `openpyxl(..., keep_links=False)` and the extension allowlist as defense in depth.

### F-03 - Medium - strict CORS defaults omit the frontend origin observed in the live flow

- **Location:** `backend/app/config.py:30-32`, `backend/tests/test_api_contract.py:59`, `backend/tests/test_security.py:76-95`.
- **Evidence:** defaults and tests allow only ports 5173 on localhost/127.0.0.1. The live Lovable/Vite flow used port 8080 and was denied. Denial is the secure behavior, but the requested frontend integration does not work with the default configuration.
- **Exploit scenario:** this is primarily availability/configuration, not data disclosure. A user may work around it by setting a wildcard origin, which would create a local-service browser attack surface.
- **Required fix:** add only the exact observed local 8080 origins, or set `DOCTRACE_CORS_ORIGINS` explicitly in the documented dev command. Do not use wildcard or origin regex matching. Test both allowed 5173/8080 origins and a denied attacker origin.

### F-04 - Medium - final negative security suite is not currently executable

- **Location:** `backend/tests/test_security.py:7`, `backend/tests/test_security.py:40-149`.
- **Evidence:** the file imports `fastapi.testclient.TestClient`; the full suite hung without output in the current FastAPI/Starlette/httpx combination. The suite does not currently prove parser timeout/queue handling, encrypted/external Office rejection, review/audit cross-workspace behavior, transaction rollback, or offline network blocking.
- **Exploit scenario:** regressions in high-risk boundaries can ship while the headline unit suite remains green.
- **Required fix:** use an `httpx.AsyncClient` with `ASGITransport` (and explicit lifespan handling if required), make every security test bounded, and add the missing cases from the early gate test plan.

### F-05 - Low - Python supply-chain verification is not reproducible

- **Location:** `backend/requirements.txt:1-14`.
- **Evidence:** compatible ranges are used without a fully resolved lock/hashes, and `pip-audit` was unavailable. `pip check` is clean, but that checks consistency rather than known vulnerabilities.
- **Exploit scenario:** separate installs can resolve different parser/native-library versions, complicating patch response and offline reproduction.
- **Required fix:** produce a reviewed Python 3.11 lock with hashes for the supported platform, retain the human-readable input requirements, and run a Python vulnerability/license scanner in CI or release preparation.

### Control disposition

| Early requirement | Result | Evidence |
| --- | --- | --- |
| 1. Stream 25 MiB, safe server path, partial cleanup | Pass | `processing.py:116-150`; oversized/path tests exist. |
| 2. Extension plus content validation, empty/corrupt/mismatch rejection | Pass | `processing.py:36-114`; generated robustness fixtures and tests. |
| 3. Hostile Office container controls | Partial | Expansion/traversal/signature pass; encryption/external-target checks remain F-02. |
| 4. Bounded isolated parser/OCR execution | **Fail - High** | F-01. |
| 5. Originals outside web root, unpredictable names, never executed | Pass | UUID path at `processing.py:142-144`; no file-serving route. OS ACL hardening remains operational guidance. |
| 6. Exact CORS | Partial | Exact allowlist/no credentials pass; active dev port mismatch is F-03. |
| 7. Workspace/resource isolation and derived audit scope | Pass for local single-user scope | Collection queries filter workspace; review routes derive `workspace_id` from stored targets. Singleton IDs are global opaque IDs and are not a tenant boundary; remote/multi-user use still requires authenticated ownership checks. |
| 8. Validation, parameterized queries, safe errors | Pass | Pydantic length/enums, SQLAlchemy expressions and controlled error details. |
| 9. SQLite integrity and recompute rollback | Pass by inspection | Foreign keys/WAL enabled; review plus audit commit together; recompute is one transaction. Failure/rollback concurrency tests remain needed. |
| 10. Offline runtime | Pass by inspection | No outbound HTTP/model-download code; local optional adapter fallback. Add an enforced network-block test. |
| 11. Content-free logs and append-only audit API | Pass | Logs use generated IDs/error types; no audit update/delete endpoint. |
| 12. Retention/deletion/backup policy | Partial | Documentation warns that deletion/export is unsupported and database plus originals must be handled together; no lifecycle endpoint exists in the fixed contract. Complete deletion and restore testing are required before real regulated documents. |

## Final security rerun - 2026-11-14

**Verdict: PASS with Medium findings for the supported loopback-only, single-user scope.** No Critical or High finding remains open. This rerun supersedes the earlier `Final implementation gate` verdict above: the bounded queue, killable extraction subprocess, Office-container checks and exact 5173/8080 CORS allowlist have since been implemented. The service is still not approved for remote or multi-user exposure.

### Rerun evidence

- `python -m pytest -q backend/tests/test_regressions.py backend/tests/test_api_contract.py backend/tests/test_extraction.py backend/tests/test_normalization.py` passed: **17 passed in 3.61s**. This covers queue saturation, external Office relationships, exact CORS configuration, recompute/review preservation, API contract, extraction and normalization.
- Focused live CORS/security-header validation passed: `test_cors_and_security_headers_allow_only_configured_vite_origins` (**1 passed in 2.86s**). All four configured loopback origins were accepted and the attacker origin was denied.
- Focused malformed-upload validation did not pass: `test_upload_validation_limits_sanitization_and_error_hygiene` failed on Windows because cleanup of a corrupted PDF raised `PermissionError` at `backend/app/processing.py:166`. This is F-06 below.
- `python -m pip check` reported `No broken requirements found`.
- `npm audit --offline --audit-level=high` reported `found 0 vulnerabilities` from the checked-in lockfile.
- A repository secret-pattern scan excluding dependencies, generated test documents and runtime data found no candidate credential or private key. Git-history scanning remains unavailable because this directory is not a Git worktree.
- Static runtime-network inspection found no outbound HTTP client, model download or telemetry call under `backend/app`. RapidOCR is imported locally and the non-OCR fallback fails closed.

### Closed blocking findings

- **Prior F-01 closed:** `backend/app/processing.py:27-28,176-185` bounds active plus pending jobs with a `BoundedSemaphore` and returns overload explicitly; `backend/app/processing.py:197-220` runs extraction in a spawned subprocess, applies a deadline and terminates/kills a stuck child. Queue-full upload cleanup is handled at `backend/app/main.py:152-156`.
- **Prior F-02 closed:** `backend/app/processing.py:77-94` rejects encrypted ZIP entries, macro-enabled Office content types and external Office relationship targets in addition to expansion/traversal controls.
- **Prior F-03 closed:** `backend/app/config.py:33-37` contains exact localhost and `127.0.0.1` origins on ports 5173 and 8080; `backend/app/main.py:57-64` disables credentials and limits methods and headers.
- **Prior F-04 closed for the blocking cases:** the focused regression/security tests execute with bounded local clients and cover queue saturation, Office external links and CORS. A direct extraction-timeout regression test is still desirable, but the implemented termination path is clear and the absence of that extra test is not itself a High finding.

### F-06 - Medium - malformed PDF cleanup can become an uncaught Windows error

- **Location:** `backend/app/processing.py:103-114`, `backend/app/processing.py:154-166`; failing assertion path at `backend/tests/test_security.py:39-67`.
- **Evidence:** the corrupted-PDF case reaches the `finally` cleanup, but the temporary file can remain locked by PyMuPDF after an open failure. `temp_path.unlink(missing_ok=True)` then raises `PermissionError`, escaping the intended safe HTTP 415 response. The focused test failed with `[WinError 32]`.
- **Exploit scenario:** a local user repeatedly uploads malformed PDFs. Requests return an internal error and locked temporary files can accumulate until the process exits, reducing availability and leaking an internal filesystem path to development error handling. The 25 MiB request cap, loopback boundary and bounded job queue keep this below High severity in the supported scope.
- **Required fix:** guarantee parser-handle release on failed PDF open and make temporary cleanup bounded and resilient to transient Windows sharing violations. Preserve the original safe 415 response, log only a generated ID/error class, and add an assertion that no `doctrace-*` temporary file remains after every rejected upload.

### F-07 - Medium - parser child has a deadline but no OS memory/CPU/privilege sandbox

- **Location:** `backend/app/processing.py:197-220`.
- **Evidence:** the subprocess is killable after the configured deadline, and input page/pixel/archive limits plus queue bounds are present. The child nevertheless runs as the same OS user without a Job Object/container memory cap, CPU quota or reduced token.
- **Exploit scenario:** a size-valid malicious document causes a native parser to consume host memory or CPU rapidly before the deadline, affecting the local desktop.
- **Required fix:** before processing untrusted real-world documents at scale, run extraction under a lower-privilege identity and enforce OS-level memory/CPU/process limits (for example, a Windows Job Object or an isolated worker container). Keep the current timeout and format limits as defense in depth.

### F-08 - Medium - remote exposure is configuration-sensitive and unsupported

- **Location:** supported startup/bind documentation and `backend/app/main.py:57-64`.
- **Evidence:** CORS is exact and credentials are disabled, but the application has no authentication or tenant authorization by design. Python/uvicorn can still be manually started on `0.0.0.0`; CORS does not protect non-browser clients.
- **Exploit scenario:** an operator binds or proxies the service beyond loopback and unintentionally exposes stored documents, search, analysis and review mutations to unauthenticated clients.
- **Required fix:** retain `127.0.0.1` in all supported start commands and explicitly reject/document remote binds. Before any remote or multi-user deployment, add authentication, per-user authorization, TLS, quotas, CSRF/session controls where applicable and a new threat model.

### F-09 - Low - Python dependency verification is not fully reproducible

- **Location:** `backend/requirements.txt:1-14`.
- **Evidence:** dependency ranges are not a hash-locked resolution and `pip-audit` is not installed. `pip check` is clean; that proves compatibility, not absence of published vulnerabilities. RapidOCR is mandatory in the manifest even though the runtime supports an unavailable-OCR fallback, increasing the native dependency surface.
- **Exploit scenario:** separate offline installs resolve different native parser/OCR builds, complicating vulnerability response and repeatable release validation.
- **Required fix:** produce and review a Python 3.11 lock with hashes for the supported Windows platform, scan it in release preparation, and consider moving RapidOCR into an explicit optional extra.

### Final control disposition

| Area | Result | Evidence / boundary |
| --- | --- | --- |
| Critical/High findings | **Pass** | None open in the supported loopback-only, single-user scope. |
| Upload allowlist, signatures and limits | Partial | Size/signature/archive/page/pixel controls pass inspection; corrupted-PDF cleanup is F-06. |
| Queue and parser timeout | Pass | Bounded submission plus spawned, terminable child process. OS resource sandbox remains F-07. |
| Office hostile features | Pass | Encrypted entries, macros and external relationships are rejected. |
| CORS and browser headers | Pass | Exact four-origin loopback allowlist, no credentials, limited methods/headers, denial test passing. |
| Workspace scope and review/audit integrity | Pass for local scope | Collection queries are workspace filtered; mutation scope comes from stored targets; recompute regression preserves reviewed IDs/statuses and audit targets. Authenticated ownership is required for multi-user use. |
| Error/log privacy | Partial | Routine logs and background failures are content-free; F-06 is an uncaught cleanup path. |
| Offline runtime / SSRF | Pass by inspection | No runtime outbound network path found; local OCR import/fallback only. |
| Dependency/secrets | Partial | npm offline audit and pip consistency pass; no candidate secrets; Python lock/vulnerability audit remains F-09. |
| Retention, deletion and backups | Partial | No deletion/export lifecycle endpoint; do not use for regulated documents until policy and complete deletion/restore testing exist. |

The security gate therefore passes only for the documented local loopback demo. F-06 should be fixed before calling the negative upload suite fully green; F-07 through F-09 remain hardening work and become more serious if the deployment boundary expands.

## Final post-fix security gate - 2026-11-15

**Verdict: PASS with Medium residual risks for the documented loopback-only, single-user scope.** No Critical or High finding remains open. This section supersedes the earlier implementation-gate and rerun verdicts above. Remote or multi-user exposure remains explicitly unsupported.

### Final verification evidence

- `python -m pytest backend/tests/test_security.py backend/tests/test_regressions.py -q` passed: **17 passed in 4.59 seconds**. The suite covers streamed upload limits and cleanup, sanitized storage names, corrupted and mismatched content, exact CORS and security headers, workspace isolation, document-local OCR failure, encrypted/macro/external Office rejection, queue saturation, child-process timeout termination, review/audit preservation, and the Windows cleanup regression.
- The complete backend suite subsequently passed twice with **31/31 tests**, as recorded in `docs/test-report.md`.
- `python -m pip check` returned `No broken requirements found`.
- `npm audit --offline --audit-level=high` returned `found 0 vulnerabilities` for the installed lockfile.
- A secret-pattern scan excluding dependencies, generated documents, runtime data and the lockfile found no candidate private key, AWS access key, OpenAI-style token or hard-coded password. This directory is not a Git worktree, so history scanning was not available.
- Static inspection confirmed a bounded submission semaphore; spawned, killable extraction with a deadline; page, pixel and Office-expansion limits; UUID server-side filenames; exact loopback CORS origins; no credentialed CORS; workspace-filtered collection queries; database-derived mutation/audit scope; content-free routine logs; and no outbound HTTP/model-download code in `backend/app`.

### Closed final finding

- **F-06 closed:** `processing.py::_unlink_with_retry` now handles transient Windows sharing violations without masking the intended safe upload error. `test_invalid_pdf_cleanup_retries_windows_lock_without_masking_415` and the complete negative upload test both pass.

### Remaining Medium risks

1. **No OS-level parser resource sandbox.** Extraction is bounded and killable, but its child process runs as the same OS user without a Windows Job Object/container memory cap, CPU quota or reduced token. Use a lower-privilege worker and OS resource limits before processing untrusted documents at scale.
2. **Remote exposure is unsupported.** There is intentionally no authentication, tenant authorization or TLS. CORS does not protect non-browser clients. Keep every supported command bound to `127.0.0.1`; add identity, object authorization, TLS, quotas and a fresh threat model before proxying, tunnelling or binding remotely.
3. **Python supply-chain verification is not fully reproducible.** Compatible version ranges and `pip check` prove install consistency, not absence of published vulnerabilities. Produce a reviewed Python 3.11 lock with hashes and run a vulnerability/license scan for release preparation.
4. **Deletion/export and retention are not productized.** Backup guidance is present, but no complete deletion/export workflow exists. Do not claim erasure/portability support or use the build for regulated data at scale until lifecycle controls and restore/deletion tests are implemented.

The final security gate is therefore green only within the documented local demo boundary.
