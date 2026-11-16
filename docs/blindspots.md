# RECORDLINE Independent Code Review and Blind-Spot Audit

Review date: 2026-11-15  
Verdict: **Approve with Medium follow-ups for the documented loopback-only, single-user scope.** No Critical or High correctness or security finding remains open in the reviewed implementation. This verdict does not approve remote or multi-user deployment.

## Verification performed

- `.venv\Scripts\python.exe -m pytest backend/tests/test_regressions.py backend/tests/test_api_contract.py backend/tests/test_extraction.py backend/tests/test_normalization.py -q` — **21 passed in 3.53s** under Python 3.12.14.
- `.venv\Scripts\python.exe backend/evaluate.py` — completed and regenerated `evaluation_report.md` from the generated ground truth.
- Read the production ingestion, extraction, analysis, API and persistence paths; generator and ground truth; strict acceptance and security tests; evaluation implementation and report; frontend API boundary; and security, privacy and deployment documents.
- The separate full-corpus acceptance run was still executing when this audit closed. The parent QA gate must retain its result as release evidence; this review does not substitute for that run.

## Previously blocking findings now closed

### Shared production/evaluation relationship implementation

- `backend/app/analysis.py` now owns `build_relationship_signals`, `score_relationship`, `_relationship_type` and `select_relationship_evidence`.
- Runtime recomputation and `backend/evaluate.py` call those same functions. The semantic signal is a fitted unigram/bigram TF-IDF cosine value, not the former set-token proxy.
- The evaluator scores typed triples. A wrong type on a labelled pair is both a false positive and a false negative rather than a pair-only success.
- `test_runtime_relationship_signals_are_real_tfidf` and the acceptance relationship-type assertions cover the regression.

### Review decisions and audit targets survive recompute

- `recompute_workspace` carries forward relationship IDs/statuses by document pair and conflict IDs/statuses by canonical field plus normalized value set.
- `test_recompute_preserves_review_ids_statuses_and_audit_targets` and the HTTP acceptance workflow verify confirm/reject, recompute, stable IDs/statuses and resolvable audit targets.

### Upload work is bounded and extraction is killable

- `backend/app/processing.py` bounds active plus pending jobs with a `BoundedSemaphore` and returns a safe 503 when capacity is exhausted.
- Extraction runs in a spawned subprocess with a deadline and terminate/kill fallback. ZIP expansion, PDF page, raster pixel and upload-byte limits are enforced.
- Office external relationships, encrypted entries and macro-enabled content are rejected. Temporary-upload cleanup retries transient Windows locks without replacing the intended safe 415 response.
- Queue-full, timeout, hostile Office and cleanup regressions are present.

### Evidence and timeline metrics are now substantive

- Relationship evidence requires the expected type, passages from both endpoint documents and reason-relevant text, project ID or normalized amount support. Conflict evidence is checked against independently generated expected facts.
- Timeline accuracy requires exact `eventDate`, exact `fileDate` and a source passage containing the independently expected date.
- The image upload path no longer relies on source filesystem mtime: the generator embeds PNG `Creation Time` and JPEG EXIF dates, and production reads both. `test_image_story_dates_come_from_embedded_metadata_after_upload_copy` covers the copied-upload case.
- The current synthetic evaluation reports exact timeline and OCR amount accuracy on the labelled fixtures. These remain small synthetic regression results, not real-world accuracy claims.

### Frontend/backend seam follows the project rules

- Screens consume data through `src/api/hooks.ts`; `src/api/client.ts` is the single mock-versus-HTTP switch, and only `src/api/mockApi.ts` imports demo data.
- Workspace hooks receive explicit route-scoped IDs. Mock responses remain workspace-scoped and do not manufacture extracted evidence for uploads.
- The HTTP client covers every fixed endpoint, polling is driven by backend document status, and derived views are invalidated as processing/reviews change.

## Remaining findings

### Medium — Reported relationship precision is precision over labelled predictions, not all emitted edges

- **Location:** `backend/evaluate.py:_relationship_prf`; generated `evaluation_report.md`.
- **Evidence:** the evaluator counts a prediction as a false positive only when it is an explicit `mustNotLink` pair or a wrong type for an expected pair. Other unlabelled predictions are excluded from the denominator. In the current run, hybrid emits 25 dev relationships while only 10 are labelled; held-out emits 6 while 4 are labelled.
- **Impact:** a headline of `100% precision` can be read as corpus-wide precision even though 15 dev edges and 2 held-out edges are not judged. This is defensible for partial labels, but it is not ordinary closed-world precision.
- **Required follow-up:** label every possible pair as positive/negative before calling the metric overall precision, or rename it `labelled precision` in JSON, the Markdown table and final report. Continue reporting total predictions, labelled predictions and must-not violations together.

### Medium — Review carry-forward keys do not encode the full reviewed finding

- **Location:** `backend/app/analysis.py:recompute_workspace` and `_build_conflicts`.
- **Evidence:** relationship decisions are keyed by unordered document pair, not pair plus relationship type. Conflict decisions are keyed by canonical field plus normalized value set, not the complete participating fact/document set.
- **Impact:** if later analysis changes a relationship type or expands a conflict while retaining the same values, an old confirmation/rejection can silently apply to a materially changed finding. The current corpus and recompute tests do not trigger that mutation.
- **Required follow-up:** key review decisions by a stable semantic fingerprint, or mark a finding pending whenever its type/evidence/participating facts change. Append an audit transition explaining the invalidation.

### Medium — Parser isolation lacks OS resource and privilege limits

- **Location:** `backend/app/processing.py:extract_isolated`.
- **Evidence:** the child is killable after a deadline but runs as the same OS user, without a Windows Job Object/container memory cap, CPU quota or reduced token.
- **Impact:** a size-valid malicious parser input may consume substantial memory or CPU before the timeout. Format, page, pixel, queue and time limits reduce but do not eliminate this local availability risk.
- **Required follow-up:** before untrusted real-document use at scale, apply OS-level memory/CPU/process limits and a lower-privilege execution boundary.

### Medium — Supported Python 3.11 release and dependency set are not reproducibly verified

- **Evidence:** local verification uses Python 3.12.14, while the launcher intentionally requires Python 3.11. Requirements use compatible ranges rather than a reviewed hash-locked resolution, and no Python vulnerability scanner result is available.
- **Impact:** the declared runtime can differ from the tested one, and fresh offline installs may resolve different native parser/OCR versions.
- **Required follow-up:** produce a Python 3.11 lock with hashes for the supported Windows platform and run generator determinism, backend tests twice, evaluation, demo load and smoke under that interpreter in CI/release preparation.

### Medium — Data lifecycle remains operational rather than productized

- **Evidence:** there is no workspace/document deletion or export API. Backup/restore guidance exists, but complete erasure, retention and restore are not automated product controls.
- **Impact:** the tool should not claim deletion, portability or regulated-data compliance. Database and originals can diverge if handled manually.
- **Required follow-up:** before real or regulated documents, add and test atomic deletion/export, retention, matching database/files backups, restore, restrictive ACLs and incident ownership.

### Low — Some review documentation still contains superseded findings

- **Evidence:** `docs/security-review.md` preserves the original design gate and an earlier final rerun that still lists the Windows malformed-PDF cleanup issue, although `_unlink_with_retry` and its regression test now exist.
- **Impact:** readers may mistake historical findings for current blockers.
- **Required follow-up:** add a dated final addendum instead of deleting history, explicitly closing the cleanup finding and citing the latest full-suite result.

### Low — Accessibility/performance follow-ups remain

- The independent accessibility/performance gate reports no High issue. Remaining items are modal focus handling, destructive-text contrast, a skip link and the roughly 550 kB shared client chunk. These should be scheduled but do not block the local acceptance build.

## Evaluation interpretation

The regenerated report is internally consistent about its tiny synthetic scope and held-out non-tuning rule. Current labelled results are:

- Dev keyword/entity and hybrid: 100% labelled relationship precision/recall/F1, zero must-not violations, 100% conflict precision/recall, evidence, timeline, OCR amount and expected fact accuracy.
- Dev semantic-only: 0% relationship recall/F1 and 0% conflict recall; this is a useful negative baseline rather than a hidden success.
- Held-out keyword/entity and hybrid: 100% labelled relationship precision/recall/F1 with zero trap violations, 100% evidence/timeline/fact accuracy. The held-out conflict score is an empty-set result because the held-out projects contain no expected conflicts.
- Held-out semantic-only: 0% relationship recall/F1. OCR is N/A because the held-out set has no OCR-labelled values.

All figures above are from 22 scenario documents in a deterministic synthetic corpus. They are regression evidence only.

## Blind spots before broader use

### Critical before any remote or multi-user launch

- Add authentication, per-user/object authorization, TLS, quotas, session/CSRF design where applicable, tenant-aware deletion/export and a new privacy/security assessment.
- Do not bind to `0.0.0.0`, proxy, tunnel or publish the port while the API remains unauthenticated.

### Should do before real documents

- Harden parser workers with OS-enforced resource and privilege limits.
- Resolve and scan a hash-locked Python 3.11 dependency set; define native parser/OCR patch cadence.
- Implement complete deletion/export, retention, encrypted backup/restore and restrictive data-directory permissions.
- Add privacy-safe queue depth, duration, disk-space and interrupted-job diagnostics.
- Expand held-out fixtures with more layouts, languages, near-matches and adversarial OCR while keeping them out of tuning.

## Approval conditions

The code-review gate is approved for the current local-only milestone once the parent QA run records a passing full backend suite twice and the live backend/frontend flow completes. The Medium findings above are required follow-ups before claims beyond this small synthetic, loopback-only build.
