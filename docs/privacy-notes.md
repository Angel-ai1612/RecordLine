# RECORDLINE Privacy and Data-Lifecycle Notes

Review date: 2026-11-14. This is engineering guidance, not legal advice. The current scope is a local, single-user tool bound to `127.0.0.1`, with no authentication, telemetry, cloud service, runtime model download, or outbound LLM call. Those assumptions materially limit exposure, but they do not make uploaded documents non-sensitive. Obtain qualified legal review before selling RECORDLINE, processing personal or regulated data at scale, or making it remotely accessible.

## Current data inventory

| Data | Purpose | Planned storage | Current access boundary | Lifecycle concern |
| --- | --- | --- | --- | --- |
| Workspace name and opaque ID | Separate analysis collections | SQLite `workspaces` | Any local caller of the unauthenticated loopback API | May itself reveal a client, case, patient, or project name |
| Original filename, type, dates, hash, status and generated storage path | Ingestion, deduplication, provenance and processing | SQLite `documents`; UUID-named original under `backend/data/files/` | Local API exposes display filename/metadata; original is not directly served | Original filename may contain personal data; stored path must never be exposed |
| Uploaded PDF, DOCX, XLSX and image bytes | Source evidence and reprocessing | `backend/data/files/` | Local service process and OS users with filesystem access | Highest-sensitivity copy; must be deleted and backed up with the database |
| Passages, locators, highlights and OCR confidence | Exact source citations | SQLite `passages` | Passage/search/answer APIs | May reproduce sensitive source text; search results can reveal content |
| Entities, facts, normalized values and statuses | Deterministic analysis | SQLite analysis tables | Graph/conflict/ask APIs | May include people, organizations, money, dates and inferred associations |
| Relationships, conflicts and timeline events | Evidence review and chronology | SQLite derived tables with passage evidence | Graph/conflict/timeline APIs | Derived links can be sensitive or misleading; product must keep them reviewable and evidence-linked |
| Review audit rows | Accountability for confirmed/rejected items | Append-only SQLite `audit` | Audit API | Actor is presently a local label, not authenticated identity; audit is not non-repudiation |
| Search terms and questions | Fulfil the immediate request | Process memory only in the planned architecture | Local service process | Must not be logged or persisted by default; they can contain copied sensitive text |
| Deterministic answer text and citations | Return evidence-based answers | Response/process memory only in the planned architecture | Requesting local browser | Must not be logged or cached beyond normal browser/process behavior |
| Operational events (ID, stage, duration, mode, safe error code) | Troubleshooting and health | Local application logs if enabled | Local OS users allowed to read logs | Logs must exclude raw filenames, document text, queries, answers, paths and stack traces |
| Synthetic development corpus | Testing and evaluation | `backend/tests/data/` | Repository users | Must remain fictional and clearly separated from real uploads |

The design uses no analytics, advertising tracker, cookie, external processor, or cross-border transfer. Optional OCR, spaCy and embedding components must load only trusted local artifacts. If any telemetry, crash reporting, cloud backup, hosted model, support upload, or external authentication provider is later added, it becomes a processor/data-transfer decision and requires this inventory, notices, consent/legal basis, contracts and settings to be reassessed.

## Retention, deletion, export and backups

The fixed frontend contract has no workspace/document deletion or data-export endpoint. Therefore the current build must not claim user-facing deletion, erasure, portability, or export support. Internal test cleanup may cascade database rows and remove originals, but that is not a product lifecycle control.

Before using real documents:

1. Define a written retention period and purpose for originals, extracted passages, derived analysis, audit rows, logs and backups. Default to the shortest practical period; do not retain uploads indefinitely merely because storage is local.
2. Add an explicit, tested deletion workflow owned by the backend lead. A workspace deletion must atomically identify and remove database rows, originals, temporary files, OCR artifacts and queued work. Define whether audit entries are deleted, minimized, or retained under a documented legal/business obligation.
3. Add a user export workflow if the product is used for another person's data or offered commercially. Export should include originals, metadata, extracted passages, derived records, review history and evidence references in a usable format.
4. Treat `backend/data/doctrace.db` and `backend/data/files/` as one consistency unit for backup and restore. Encrypt backups, restrict access, assign an owner, test restore, apply the same retention/deletion schedule, and document how expired backup copies are removed.
5. Verify temporary upload/OCR files are removed after success, rejection, timeout and crash recovery. Secure deletion cannot be guaranteed on modern SSDs; rely on full-disk encryption, restrictive ACLs and cryptographic erasure/volume disposal procedures where risk requires it.

## Access, security and transparency

- Current access is protected only by loopback binding and local OS account controls. Use full-disk encryption, restrictive permissions on `backend/data/` and backups, an automatic screen lock, and a non-shared OS account for real documents.
- Workspace IDs are isolation keys, not user authorization. Any remote, proxied, container-published, tunneled or multi-user use requires authentication, per-user/object authorization, TLS, session/CSRF design where applicable, quotas, secure account deletion/export, and a fresh privacy impact assessment.
- Evidence-based results remain potential relationships or inconsistencies. The interface and documentation must not imply that an inferred link is proof, that a different value is automatically wrong, or that an audit action identifies a legally accountable person.
- Provide clear notice before upload: what is stored, that processing is local, active OCR/similarity modes, limitations, retention, deletion/export availability, and who can access the computer and backups.
- Do not use real uploaded documents to tune rules, thresholds or models without a separately documented purpose, legal basis/consent where applicable, minimization, de-identification, retention limit and opt-out or alternative.

## Sensitive, regulated and children's data

RECORDLINE can ingest arbitrary records and may encounter health, education, financial, employment, identity, location, legal-case, biometric or children's data. The MedSaathi name is fictional test data and does not make the product suitable for real patient information. Before such use, perform a data protection impact/risk assessment; determine applicable duties (for example GDPR/UK GDPR, CCPA/CPRA, HIPAA or local health/education laws); document lawful purpose and access controls; and obtain qualified legal/security review. Do not market the current local build as compliant with any named regime.

If children may be data subjects or users, establish age/guardian rules, minimize collection, prohibit behavioral advertising, use child-appropriate notices, and obtain specialist legal review before launch. The current build has no age or consent controls.

## Likely commercial obligations

Before selling or collecting data at scale, owners should expect to need:

- a lawyer-reviewed privacy notice and terms that match actual behavior, including local storage, optional components, retention, deletion/export, security limitations and support access;
- a documented lawful basis/purpose per category, data-subject request process, identity verification and response tracking;
- processor/vendor agreements and cross-border safeguards for any future hosting, telemetry, support, backup or model provider;
- a cookie/consent assessment if analytics or non-essential browser storage is introduced;
- records of processing, privacy-by-design reviews, incident response and applicable breach notification procedures;
- a process for dependency/model provenance, security updates and handling requests to correct disputed derived records.

## Incident basics

Before real use, name an incident owner and keep a short runbook: isolate the service/device without destroying evidence; preserve privacy-safe logs; identify affected originals, extracts, backups and accounts; rotate any exposed credentials; assess notification duties with legal counsel; communicate without exposing additional document content; restore from a tested clean backup; and record corrective actions. A lost or compromised device containing the database, originals or backups is a potential data incident even when RECORDLINE made no network call.

## Prioritized gaps and owners

### Critical before remote or multi-user use

- **Authentication, object authorization, TLS and account lifecycle** — backend/security/devops. The fixed local API has no identity boundary.
- **Deletion/export and tenant-aware retention** — product/backend/privacy. Current endpoints cannot fulfil erasure or portability requests.
- **Fresh privacy and security assessment** — privacy/security/legal. Remote exposure changes processors, access, notices and breach risk.

### Should do before real documents

- **Written retention schedule and complete cleanup tests** — product/backend/QA.
- **Encrypted, access-controlled, restore-tested backups** — devops/security.
- **Full-disk encryption and restrictive data-directory permissions** — user/devops.
- **Upload notice, privacy policy and disputed-result correction process** — product/docs/legal.
- **Privacy-safe logging and network-offline verification** — backend/QA/security.
- **Incident response owner and breach runbook** — product/security/legal.

### Nice to have for synthetic-only development

- A privacy-preserving diagnostics command that reports modes, generated IDs and failure codes without filenames or content — backend/devops.
- Automated scans preventing `backend/data/`, logs and temporary upload artifacts from entering source control — security/devops.
- A visible synthetic-data badge in demo/evaluation output — frontend/docs.

## Verification checklist for the final gate

- Confirm no routine logs include document text, raw filenames, search terms, questions, answers, local paths or stack traces.
- Confirm runtime does not contact networks or download models in every advertised fallback mode.
- Confirm original, temporary and derived data locations are documented and excluded from source control.
- Confirm a backup contains matching database and originals, restores successfully, and follows the retention schedule.
- If deletion/export is not implemented, describe it explicitly as unsupported; do not imply otherwise.
- Confirm no telemetry, analytics, cookie or external processor was added without updating this document and user-facing notices.
- Confirm synthetic fixtures contain no real personal data and evaluation results are not presented as general accuracy claims.
