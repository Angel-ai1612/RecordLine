# Project Log

## 2026-11-16 - RECORDLINE documentation refresh

- Request: Produce comprehensive project documentation under the product name RECORDLINE, including objectives, architecture, languages/frameworks, algorithms, methodology, and UML/use-case/other diagrams; replace reader-facing DocTrace naming in documentation while preserving technical `DOCTRACE_*` configuration identifiers.
- Classification: docs; architecture, frontend, backend, data, security/privacy; size M. Risk flags: local uploaded document content, persistence, OCR/parser processing.
- Team: orchestrator, read-only architect and security reviewers, then docs writer. No application code changes are authorized.
- Delivered: added `docs/RECORDLINE.md` as the master technical reference with objectives, stack, architecture, data/API model, algorithms, methodology, local-only operations, limitations, traceability, and nine Mermaid UML/use-case/context/flow diagrams. Updated reader-facing documentation titles and product prose to RECORDLINE while preserving `DOCTRACE_*`, `doctrace.db`, and other source-level compatibility identifiers.
- Verification: `npm run build` passed. Existing non-blocking client-chunk warning above 500 kB remains; no application behavior was changed.

## 2026-11-14 - DocTrace real backend kickoff

- Request: Build an offline-first FastAPI/SQLAlchemy/SQLite backend matching the existing React API contract, generate a deterministic synthetic acceptance corpus, connect the frontend, and evaluate three retrieval/relationship methods.
- Classification: build; frontend, backend, data, security, infra, docs; size XL.
- Risk flags: untrusted file uploads, potentially sensitive document contents, OCR/native parsers, local persistence, background processing, audit records.
- Assumptions: local single-user system bound to `127.0.0.1`; no authentication or public deployment; no runtime network/LLM calls; `.eml` unsupported unless added without changing the frontend contract; optional heavy NLP/OCR components degrade gracefully.
- Constraints: frontend API names/shapes remain fixed; all conclusions retain source-passage evidence; deterministic code decides dates, amounts, and conflicts; held-out data is never used for tuning.
- Team: orchestrator plus architect, test-writer/data-fixture builder, early security lead; backend, QA, reviewers, devops, blind-spot, and docs roles follow in later waves.
- Environment note: the provided directory is not a Git worktree (`git status` reports no repository), so no commits or history operations are possible here.

## 2026-11-15 - Final integrated verification

- Team roles completed: architecture, deterministic data/ground truth, backend, frontend integration, evaluation, QA, security, blind-spot/code review, accessibility/performance, devops/privacy, debugging, and documentation.
- Corpus: 22 scenario documents (14 development, 8 held-out), 14 true relationships, 5 must-not-link traps, 24 expected facts, 2 expected conflicts, 4 expected non-conflicts, 16 expected timeline events, and robustness fixtures. Two generator runs produced the same `EDE3F2CE...9D3D` manifest hash and verified rupee extraction.
- Backend verification: strict generated-corpus acceptance passed; the complete 31-test suite passed twice (15.33 s and 15.18 s); focused security/regression checks passed 17/17; `pip check` was clean.
- Frontend verification: 17/17 Vitest assertions passed and the production build passed. The known 549.88 kB shared-client chunk warning remains a Medium performance follow-up.
- Evaluation: keyword/entity, semantic TF-IDF, and hybrid were run separately on development and held-out splits. Hybrid reached 100% on annotated synthetic relationship, conflict, evidence, fact, timeline, and available OCR targets. Relationship precision is labelled precision over annotated positives and explicit negatives; unlabelled predicted pairs remain unknown. These are small synthetic regression results, not general accuracy claims.
- Live proof: the corrected backpressure-aware demo loader made all 14 documents ready in workspace `ws-b23eb5be9ed8496b868d4f02b8f6d929`; the smoke script passed and dereferenced answer, relationship, and timeline evidence. Browser verification covered Documents, Graph, evidence, Conflicts, review persistence, Timeline, Ask citations/ambiguity, and Audit.
- Final gates: security PASS with Medium residuals; blind-spot/code review APPROVE with Medium follow-ups; accessibility/performance PASS with Medium follow-ups; QA PASS with no Critical/High blockers.
- Remaining release checks: run on the supported Python 3.11 interpreter with a hash-locked/audited dependency set; add OS-level parser resource limits before untrusted use at scale; keep the service loopback-only until authentication/authorization/TLS exist; productize deletion/export/retention; reduce the large frontend chunk; expand exhaustive pair annotations for true relationship precision.
