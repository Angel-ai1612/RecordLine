# DocTrace Backend Task Board

| ID | Owner role | Status | Files owned | Acceptance criteria | Notes |
| --- | --- | --- | --- | --- | --- |
| P1 | architect | done | `ARCHITECTURE.md` | Plan covers schema, offline pipeline, API contract, milestones, risks, and ADRs | Verified endpoint, milestone, evidence and ADR coverage |
| D1 | test-writer | done | `backend/tests/make_test_data.py`, `backend/tests/data/**` | Deterministic multi-format dev and held-out corpus plus independent `ground_truth.json` | Independently rerun twice after image-metadata fix; identical manifest hash `EDE3F2...9D3D` |
| S1 | security-lead | done | `docs/security-review.md` | Early threat model covers uploads, local processing, CORS, storage, privacy, and abuse | 4 High design blockers routed to backend/QA |
| B1 | backend-lead | done | `backend/**` except generator-owned files | M1-M6 backend, tests, smoke flow, local-only runtime | Live 14-document demo and evidence-dereferencing smoke passed |
| Q1 | qa-lead | done | `backend/tests/**` excluding generated corpus, QA notes | Full acceptance and contract suite; format-specific evidence; run twice | 31/31 passed twice; strict corpus acceptance passed |
| F1 | frontend-lead | done | `.env.example`, `.env.local`, `package.json`, `scripts/dev_all.ps1`, minimal frontend fixes | Real backend flow connects without contract changes; frontend build/type checks pass | Build passed; 17/17 tests passed; browser flow verified |
| E1 | data/evaluation | done | `backend/evaluate.py`, `evaluation_report.md` | Dev/held-out metrics for keyword/entity, semantic, hybrid | Completed with small-synthetic and labelled-precision caveats |
| R1 | code-reviewer | done | read-only report | No High/Critical correctness or maintainability findings | Final verdict: Approve with Medium follow-ups |
| S2 | security-lead | done | `docs/security-review.md` | Final security gate; no open High/Critical | 17/17 focused checks passed; loopback-only gate green |
| O1 | devops-lead | done | `docs/deploy.md`, run scripts/config | Reproducible local setup, health check, rollback/backup notes | Backup/restore and local-only deployment documented |
| X1 | blindspot-auditor | done | `docs/blindspots.md` | Prioritized product/reliability/legal gaps | No High/Critical; labelled-precision caveat retained |
| DOC1 | docs-writer | done | `README.md`, `PROJECT_LOG.md` assistance | Verified commands, setup, limitations, milestone results | Final commands and limitations verified |
| DOC2 | architect | done | read-only repository review | Evidence-backed RECORDLINE architecture, algorithms, and diagram inventory | Identified current flattened backend layout and documentation terminology constraints |
| DOC3 | security-lead | done | read-only repository review | Accurate RECORDLINE security/privacy boundaries and limitations | No Critical/High finding within local scope; remote exposure is out of scope and unsafe |
| DOC4 | docs-writer | done | `README.md`, `ARCHITECTURE.md`, `docs/**` | Comprehensive RECORDLINE documentation with verified technical claims and diagrams | Nine Mermaid diagrams; reader-facing branding refreshed; `npm run build` passed |

