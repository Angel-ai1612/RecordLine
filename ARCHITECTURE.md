# RECORDLINE Architecture

> This historical detailed architecture uses `DOCTRACE_*` configuration and `doctrace.db` implementation identifiers. For the maintained product-level RECORDLINE reference, including UML/use-case/context diagrams, see [docs/RECORDLINE.md](docs/RECORDLINE.md).

## Scope

Build a local, single-user evidence analysis service behind the existing React client. RECORDLINE accepts PDF, DOCX, XLSX, PNG, JPEG, and image-only PDF files; preserves exact source passages; computes document relationships, potential inconsistencies, and timeline events; and answers questions only from stored evidence. It binds to `127.0.0.1`, makes no runtime network or LLM calls, and keeps the frontend API contract unchanged.

Not in this build: authentication, multi-user authorization, cloud deployment, outbound AI services, email import, or a claim of general model accuracy. `.txt` and `.eml` are explicitly unsupported uploads.

## Stack and layout

- Python 3.11, FastAPI and Pydantic: typed HTTP boundary and generated OpenAPI.
- SQLAlchemy 2.x with SQLite at `backend/data/doctrace.db`: portable ORM schema and local transactions.
- PyMuPDF, `python-docx`, and `openpyxl`: source-aware extraction for supported document formats.
- Pillow plus an `OcrEngine` interface: preprocessing and optional RapidOCR/ONNX implementation; unavailable OCR produces a readable per-document failure/warning rather than affecting other files.
- Rules and scikit-learn TF-IDF cosine similarity as the required offline baseline. Optional locally installed spaCy and FastEmbed/ONNX adapters are capability-detected; no model downloads at runtime.
- FastAPI `BackgroundTasks` plus a bounded worker executor: sufficient for this local single-process product. The database remains the source of truth for status. A durable job queue is a later production concern.

```text
backend/
  app/
    main.py config.py database.py models.py schemas.py
    api/                 # route modules matching the fixed frontend contract
    extraction/          # PDF, DOCX, XLSX, image and OCR adapters
    analysis/            # normalization, entities, facts, scoring, conflicts, timeline, ask
    services/            # upload, processing, recompute, review/audit
  config/relationship_weights.json
  data/files/            # sanitized UUID-based originals; never web-served
  tests/
    make_test_data.py
    data/heldout/
    test_*.py
  evaluate.py
  scripts/load_demo.py
  requirements.txt
```

## Persistence model

All primary keys are opaque strings/UUIDs. Every workspace-owned query joins back to `workspace_id`; foreign keys are enabled in SQLite. Timestamps are UTC ISO-8601 at the API boundary.

| Table | Essential fields and constraints |
| --- | --- |
| `workspaces` | id, unique name, created_at |
| `documents` | id, workspace_id FK, original/sanitized filename, file_type, status, uploaded_at, file_date, stored_path, sha256, processing_error, processing_warning, OCR mode; indexes on workspace/status |
| `passages` | id, document_id FK, ordinal, text, page, block/paragraph id, sheet, cell, OCR confidence, highlight start/end; unique document/ordinal |
| `entities` | id, workspace_id FK, type, canonical name |
| `document_entities` | document_id/entity_id FKs, passage_id FK, mention text; unique tuple |
| `relationships` | id, workspace_id, source/target document FKs, type, score, four signal columns, review_status, unique normalized document pair/type |
| `relationship_evidence` | relationship_id/passage_id FKs, role; at least one passage per stored relationship |
| `facts` | id, workspace/document/passage FKs, canonical field, raw/normalized value, unit, status, value span; index on workspace/field/value |
| `conflicts` | id, workspace_id FK, canonical field, explanation, severity, review_status |
| `conflict_facts` | conflict_id/fact_id FKs; at least two distinct normalized values |
| `events` | id, workspace/document/passage FKs, event_date, file_date, label; index on workspace/event_date |
| `audit` | id, workspace_id, target type/id, action, actor, note, created_at; append-only |

Deletion behavior is explicit: workspace deletion is not exposed by this contract; internal/test cleanup cascades workspace data and removes stored originals. Originals are outside the static web root. SQLAlchemy types and constraints avoid SQLite-only SQL so PostgreSQL migration remains possible.

## HTTP contract

Responses use camelCase aliases and exactly the frontend types in `src/api/types.ts`. The existing endpoints are:

- `GET /workspaces`, `POST /workspaces {name}`
- `POST /workspaces/{workspaceId}/documents` multipart field `file`
- `GET /workspaces/{workspaceId}/documents`, `GET /documents/{documentId}`
- `GET /passages/{passageId}`, `GET /workspaces/{workspaceId}/passages/search?q=`
- `GET /workspaces/{workspaceId}/graph`
- `PATCH /relationships/{relationshipId} {reviewStatus}`
- `GET /workspaces/{workspaceId}/conflicts`
- `PATCH /conflicts/{conflictId} {reviewStatus}`
- `GET /workspaces/{workspaceId}/timeline`
- `POST /workspaces/{workspaceId}/ask {question}`
- `GET /workspaces/{workspaceId}/audit`

`GET /health` is the sole additive operational endpoint and returns service status plus active similarity and OCR modes. Missing rows return 404, invalid bodies/uploads return 400/413/415/422 as appropriate, and unexpected details are logged locally but not exposed. CORS permits only configured Vite origins. `SEED_DEFAULT_WORKSPACE` optionally creates a configured default workspace idempotently; otherwise workspaces only come from `POST /workspaces`.

## Ingestion and evidence pipeline

1. Stream at most 25 MiB to a temporary file while hashing. Validate the lowercase extension, magic bytes/container signature, and matching supported type before atomically moving it to `data/files/<uuid>.<ext>`. Never trust or use the original filename as a path.
2. Insert a `queued` document and return immediately. A bounded worker advances it through `extracting`, optional `ocr`, `analyzing`, then `ready`; exceptions mark only that document `failed` with a safe reason.
3. Extract passages with deterministic ordinals and locators:
   - PDF: one passage per PyMuPDF text block, with one-based page and block id. Read PDF creation metadata for `fileDate`; otherwise use upload file mtime.
   - DOCX: headings/paragraphs and table rows, with stable paragraph/table-row ids. Use core-properties creation time when present.
   - XLSX: one passage per non-empty row, combining nearby label and literal values; preserve sheet and the evidence value cell (for example `Summary!B12`). Read workbook creation metadata.
   - Image/image-only PDF: rasterize, normalize contrast, deskew lightly, call the optional OCR adapter, and store text plus average confidence. If OCR is unavailable, retain the document and a clear warning/failure reason; never fabricate text.
4. Every extracted fact, relationship, conflict, event, search hit, and answer citation references real persisted passage ids. Highlight offsets are computed against the persisted passage text.
5. Recompute workspace relationships, conflicts, and timeline transactionally whenever a document becomes ready. Recompute uses a new transaction after passage/fact commit, so readers never observe half-written analysis.

## Deterministic analysis

### Entities and facts

Rules recognize project ids, INR amounts (`Rs`, `Rs.`, `INR`, `₹`, common OCR variants, and lakh notation), day-first numeric dates, and English month dates. Canonical fields include at least `project_budget`, `submission_deadline`, and `expense_item`; synonym maps cover budget/total cost/allocated funds and deadline/due date/final submission. Context windows map `proposed`, `requested`, `tentative` to `proposed`; `approved`, `sanctioned`, `confirmed` to `approved`; explicit estimate language to `estimated`; otherwise `stated`. Approval is never inferred from mere occurrence or sequence. Optional installed spaCy adds people/organizations; regex fallback always supplies project, amount, date, and item candidates.

Amounts become integer minor-independent INR strings and dates become ISO dates. Normalization and comparison are pure functions with unit tests. An OCR-specific conservative correction may change `O` to `0` only inside an amount token supported by currency/total context; the raw value remains stored.

### Relationships

For each document pair in the same workspace, compute four values in `[0,1]`:

- entity overlap: weighted Jaccard, with exact project ids dominant;
- semantic similarity: configured local embedding cosine when already installed, otherwise TF-IDF cosine;
- explicit reference: filename, exact project id, quoted title, or dated meeting/reference mention;
- temporal context: compatible chronology and close story dates, never enough alone to create a link.

Weights and threshold live in `config/relationship_weights.json`, must sum to 1, and are tuned only against the development set. Exact project-id mismatch is a strong negative guard; shared people, generic deadlines, guide names, or vocabulary alone cannot bridge projects. Each accepted edge stores evidence from both endpoints and is typed `revision_of`, `references`, `supports`, or `same_topic`. `contradicts` remains accepted by the frontend type but conflict presentation is owned by the conflict engine. Rejected relationships are excluded before connected-component clustering on recompute.

### Potential inconsistencies

Connected components of non-rejected relationships define clusters. Compare only facts in the same cluster and canonical field. A candidate requires at least two normalized values and evidence for each. It is described as a potential inconsistency, never a winner or confirmed truth.

A fully evidenced status transition is not a conflict: a later passage must explicitly approve/sanction value B, link to the earlier request/value A, and the subsequent final document must use B. The older and newer facts remain queryable, but Scenario B becomes an expected non-conflict. A proposal without approval, an unexplained later value, or a final document that still uses an older value remains reviewable. Explanations mention chronology and statuses without deciding correctness.

### Timeline, search, and ask

Events are sentences/rows with explicit dates and stored source passages. `eventDate` is the mentioned date; `fileDate` is metadata creation date or filesystem mtime, and sorting uses `(eventDate, documentId, passage ordinal)` for determinism.

Search ranks workspace-scoped passages by canonical field match, exact project/entity terms, lexical TF-IDF, and optional local semantic similarity. Ask uses the same retriever, gathers all values for a detected canonical field in the relevant relationship cluster, and renders a deterministic extractive answer with `[1]` citations in citation-array order. Differing values are all listed with document/status and an `ambiguityNote`; missing evidence is stated plainly. No generative model invents prose or facts.

## Test data and evaluation design

`backend/tests/make_test_data.py` is the single source of truth for scenarios and independently emits documents plus `ground_truth.json` with a fixed seed. It must generate byte-identical content on two runs, including stable metadata, zip member timestamps for DOCX/XLSX if necessary, and deterministic noisy images. A rupee-capable bundled/system font is embedded in PDFs and verified by extracting the generated PDF text. The dev corpus covers MedSaathi, its distractors, an explained approved change, a clean control, text PDF/DOCX/XLSX/PNG/JPEG/image-only PDF, page-three evidence, and validation fixtures. Oversize content is generated during its test. Held-out projects use distinct language, values, filenames, and traps and are never read by tuning code.

Tests cover extraction per format, locators, OCR fallback and amount normalization, facts/status, relationship signals/guards, clustering, explained-change suppression, timeline, ask citations, uploads, isolation, reviews/audit, every HTTP response shape, and real background status polling. Contract fixtures mirror `types.ts` exactly; TypeScript remains the source of truth.

`evaluate.py` runs keyword/entity-only, semantic-only, and hybrid modes against fresh databases. It reports per-format processing/accuracy plus dev and held-out relationship precision/recall/F1, conflict precision/recall, evidence accuracy, timeline accuracy, OCR amount accuracy, and processing time. It reads expected labels only from generated ground truth, not pipeline output. Reports state prominently that this is small synthetic data and not a general accuracy claim.

## Security, privacy, and operations

- Bind only to `127.0.0.1`; configure a strict origin allowlist and no credentials wildcard.
- Stream size validation, magic-byte checks, sanitized UUID paths, parser isolation via timeouts/bounded workers, and no direct file-serving route.
- No document content, filenames, or extracted text in routine logs. No telemetry or model downloads. All configuration comes from environment variables and checked-in examples contain no secrets.
- SQLite writes are short and transactional; enable WAL and foreign keys. One analysis job per workspace is serialized to prevent recompute races.
- `/health` reports capability modes, not document contents. Startup logs report active similarity/OCR modes once.
- Local backup is a consistent copy of the database plus `data/files`; restore instructions must keep both together. A public/multi-user deployment is unsafe without authentication, authorization, encryption/retention policy, stronger job durability, rate limiting, and hardened parser sandboxing.

## Milestones and ownership

1. **M1 - backend lead:** app skeleton, configuration, schema initialization, camelCase schemas, `/health`, CORS, create/list workspaces. Verify server startup and contract shapes.
2. **Dataset - test writer:** deterministic generator, dev/held-out ground truth, validation fixtures, rupee extraction self-check. Verify hashes from two clean runs match.
3. **M2 - backend lead:** secure upload, stored originals, background states, all extractors and OCR adapter. Verify every generated supported file reaches `ready` when dependencies are available; verify graceful OCR-unavailable behavior separately.
4. **M3 - backend/data:** normalization, entities, facts and statuses. Verify MedSaathi budgets/deadlines/receipt and Scenario B approval state against independent labels.
5. **M4 - backend/data:** four-signal relationships, config and dev-only tuning, graph evidence. Verify all dev true links and zero `must_not_link` false links.
6. **M5 - backend lead:** cluster-scoped potential conflicts, explained approval transitions, review patches and audit. Verify expected conflicts/non-conflicts and no cross-project comparison.
7. **M6 - backend lead:** events, passage endpoints/search and deterministic ask. Verify order, separate dates, all values, ambiguity note, and dereferenceable citations.
8. **M7 - frontend lead:** environment files, Windows-friendly run/load commands, demo loader, live contract smoke path, only minimal real frontend fixes. Verify `npm run build`, frontend tests, and an endpoint-order smoke test or browser walkthrough.
9. **M8 - data/evaluation:** three methods, per-format/dev/held-out metrics and report. No held-out tuning.
10. **Gates - QA, code review, security/privacy, devops, blind-spot:** run the entire suite twice, inspect upload/data risks, review maintainability, dry-run setup, and record launch gaps. High/Critical findings block completion.
11. **Docs - docs writer:** verified README commands, architecture, decisions, setup/troubleshooting, unsupported email, known limitations, real evaluation numbers, and project log.

## Risks and mitigations

1. **OCR dependency/model unavailable offline:** capability detection, explicit mode in health, deterministic fallback/error behavior, and separate tests for both branches.
2. **Native parsers consume excessive resources on hostile files:** strict size/type checks, bounded workers/timeouts, no executable formats, and document-local failure. Process isolation is required before untrusted public use.
3. **Tiny synthetic set encourages overfitting:** scenario definitions independent of output, held-out folder inaccessible to tuning, multiple formats/paraphrases/traps, and explicit non-generalization language.
4. **Relationship clusters leak across projects:** exact project-id mismatch guard, workspace scoping, conservative threshold, must-not-link tests, and rejected-edge exclusion.
5. **Concurrent recomputation creates partial or stale results:** workspace-level serialization, transactionally replace derived rows, deterministic ordering, and integration tests with simultaneous ready events.

## Decision records

### ADR-1: Keep the frontend contract fixed

**Date:** 2026-11-14  
**Status:** accepted

**Context:** The UI already isolates backend choice in `src/api/client.ts` and expects exact camelCase shapes.  
**Decision:** Implement those endpoints and shapes verbatim; add only `/health`.  
**Alternatives:** Redesign/version the API, rejected because it creates unnecessary frontend churn.  
**Consequences:** Internal warnings/errors remain backend-only unless represented through existing status behavior; contract tests are mandatory.

### ADR-2: Evidence is a relational invariant

**Date:** 2026-11-14  
**Status:** accepted

**Context:** Every user-visible conclusion must open an exact source.  
**Decision:** Derived records reference persisted passages through foreign keys/junctions; no edge, conflict, event, or answer citation is returned without resolvable evidence.  
**Alternatives:** Embed snippets in JSON blobs, rejected because they drift from source records.  
**Consequences:** Recompute must preserve or atomically replace evidence links and tests dereference every output.

### ADR-3: Deterministic core with optional local model adapters

**Date:** 2026-11-14  
**Status:** accepted

**Context:** Runtime must be private, offline, testable, and honest about unavailable heavy models.  
**Decision:** Rules, normalization, TF-IDF, and deterministic answer templates are required; OCR, spaCy, and local embeddings are optional adapters with explicit modes.  
**Alternatives:** Network LLM or mandatory downloaded models, rejected by privacy/offline constraints.  
**Consequences:** Quality is bounded but reproducible; evaluation reports the active method/mode.

### ADR-4: In-process background work for the local product

**Date:** 2026-11-14  
**Status:** accepted

**Context:** Uploads must return immediately, but the stated deployment is one local FastAPI process.  
**Decision:** Use a bounded in-process executor with persisted document states and workspace recompute locks.  
**Alternatives:** Celery/Redis, rejected as unnecessary installation and offline operational burden.  
**Consequences:** Jobs do not survive abrupt process termination; startup marks abandoned active states failed/requeueable. A durable queue is required for service deployment.

### ADR-5: Development tuning and held-out evaluation are physically separated

**Date:** 2026-11-14  
**Status:** accepted

**Context:** Labels derived from pipeline output or held-out-driven thresholds would make evaluation meaningless.  
**Decision:** Scenario definitions emit independent labels; tuning only reads the development section/path; held-out labels are read solely by final evaluation.  
**Alternatives:** Tune on all fixtures, rejected as leakage.  
**Consequences:** The configuration records final dev-tuned weights/threshold and evaluation reports both splits separately.
